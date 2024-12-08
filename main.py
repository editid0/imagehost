from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os, boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError


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
        return jsonify({"error": "No selected file"}), 400
    # Check file size
    file.seek(0, 2)  # Move the cursor to the end of the file
    file_size = file.tell()  # Get the cursor position, which is the file size
    file.seek(0)  # Reset cursor to the beginning of the file for upload
    if file_size > MAX_FILE_SIZE_MB:
        return jsonify({"error": "File size exceeds the 3MB limit"}), 400
    try:
        # Upload the file to R2
        s3_client.upload_fileobj(file, "image-host", file.filename)
        return (
            jsonify(
                {"message": "File uploaded successfully", "filename": file.filename}
            ),
            200,
        )

    except (NoCredentialsError, PartialCredentialsError) as e:
        return jsonify({"error": "Invalid R2 credentials"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
