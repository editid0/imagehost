import time
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
import os, boto3, io
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from uuid import uuid4


load_dotenv()

R2_S3_LINK = os.getenv("R2_S3_LINK")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
MAX_FILE_SIZE_MB = 3 * 1024 * 1024

s3_client = boto3.client(
    "s3",
    endpoint_url=R2_S3_LINK,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
)

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    # Upload the file to R2
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    # Check file size
    file.seek(0, 2)  # Move the cursor to the end of the file
    file_size = file.tell()  # Get the cursor position, which is the file size
    file.seek(0)  # Reset cursor to the beginning of the file for upload
    if file_size > MAX_FILE_SIZE_MB:
        return jsonify({"error": "File size exceeds the 3MB limit"}), 400
    deletekey = str(uuid4())
    metadata = {
        "filename": file.filename,
        "deletekey": deletekey,
    }
    filename = file.filename
    extension = filename.split(".")[-1]
    uid = str(uuid4())
    try:
        # Upload the file to R2
        s3_client.upload_fileobj(
            file, "image-host", f"{uid}.{extension}", ExtraArgs={"Metadata": metadata}
        )
        return (
            jsonify(
                {
                    "message": "File uploaded successfully",
                    "uid": uid,
                    "extension": extension,
                    "deletekey": deletekey,
                }
            ),
            200,
        )

    except (NoCredentialsError, PartialCredentialsError) as e:
        return render_template("error.html", error=str(e)), 500

    except Exception as e:
        return render_template("error.html", error=str(e)), 500


@app.route("/image/<path:filename>")
def serve_image(filename):
    # Serve the image from R2
    try:
        response = s3_client.get_object(Bucket="image-host", Key=filename)
        return send_file(
            io.BytesIO(response["Body"].read()),
            mimetype="image/jpeg",
            as_attachment=False,
            download_name=f"{filename}",
        )
    except Exception as e:
        return render_template("error.html", error=str(e)), 500


@app.route("/image/<path:filename>/frame")
def serve_frame(filename):
    deletekey = request.args.get("deletekey")
    try:
        s3_client.get_object(Bucket="image-host", Key=filename)
        return render_template("frame.html", filename=filename, deletekey=deletekey)
    except Exception as e:
        return render_template("error.html", error=f"File not found: {filename}"), 500


@app.route("/delete", methods=["GET", "POST"])
def delete():
    if request.method == "GET":
        return render_template("delete.html")
    elif request.method == "POST":
        uid = request.form.get("uid")
        deletekey = request.form.get("deletekey")
        try:
            # find the file name from the uuid prefix
            res = s3_client.list_objects(Bucket="image-host", Prefix=uid)
            if "Contents" not in res:
                return render_template("error.html", error="File not found"), 404
            # set filename
            filename = res["Contents"][0]["Key"].split("/")[-1]
            # find the image using the uid and make sure the deletekey matches
            response = s3_client.head_object(Bucket="image-host", Key=filename)
            metadata = response.get("Metadata", {})
            if metadata.get("deletekey") == deletekey:  # Metadata keys are lowercase
                # Delete the object
                s3_client.delete_object(Bucket="image-host", Key=filename)
                return (
                    render_template("error.html", error="File deleted successfully"),
                    200,
                )
            else:
                # If deleteKey doesn't match, wait 1 second and return an error
                time.sleep(1)
                return (
                    render_template("error.html", error="Delete key does not match"),
                    400,
                )
        except Exception as e:
            return render_template("error.html", error=str(e)), 500


if __name__ == "__main__":
    app.run(debug=True)
