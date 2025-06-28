import os
from flask import Flask, flash, request, redirect, url_for, send_from_directory, send_file
from werkzeug.utils import secure_filename
from functools import wraps
import base64

UPLOAD_FOLDER = '/datas'
ALLOWED_EXTENSIONS_ZIP = {'zip'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file_zip(filename: str):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS_ZIP

def login_required(f):
    def check_auth(username, password):
        if username == os.environ['ADMIN_USERNAME']:
            if password == os.environ['ADMIN_PASSWORD']:
                return True
        return False
    @wraps(f)
    def wrapped_view(**kwargs):
        auth = request.authorization
        if not (auth and check_auth(auth.username, auth.password)):
            return ('Unauthorized', 401, {
                'WWW-Authenticate': 'Basic realm="Login Required"'
            })
        return f(**kwargs)
    return wrapped_view

def get_filepath(game: str, version: str) -> str:
    return secure_filename(f"{game}_{version}.zip")

@app.route('/upload/<game>/<version>', methods=['GET', 'POST'])
@login_required
def upload_file(game: str, version: str):
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if not allowed_file_zip(file.filename):
            flash('Create a Zip file instead')
            return redirect(request.url)
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], get_filepath(game, version))
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            for chunk in file.stream:
                _ = f.write(chunk)
        # file.save(full_path)
        return redirect(url_for('finished_upload', game=game, version=version))
    return f'''
    <!doctype html>
    <title>Upload new {game}:{version} build</title>
    <h1>Upload new {game}:{version} build</h1>
    <form method="post" enctype=multipart/form-data id="fileUploadForm">
        File: <input type="file" name="file" />
        <input type="submit" value="Upload" id="btn" />
    </form>
    <p id="textProgress"></p>
    <script>
        const form = document.getElementById("fileUploadForm");
        const textProgress = document.getElementById("textProgress");
        form.addEventListener('submit', handleSubmit);

        /** @param {{Event}} event */
        async function handleSubmit(event) {{
            event.preventDefault();

            const form = event.currentTarget;
            const url = new URL(form.action);
            const formData = new FormData(form);

            const fetchOptions = {{
                method: form.method,
                body: formData,
                headers: {{
                    'Authorization': 'Basic ' + btoa('{request.authorization.username}:{request.authorization.password}'),
                }},
            }};
            textProgress.innerText = "Uploading...";
            const res = await fetch(url, fetchOptions);
            textProgress.innerText = "Uploaded...";
            if (res.redirected) {{
                window.location = res.url;
                return
            }}
            if (!res.ok) {{
                textProgress.innerText = res.status;
            }}
        }}
    </script>
    '''


@app.route('/download/<game>/<version>', methods=['GET'])
def download_file(game: str, version: str):
    return send_from_directory(app.config['UPLOAD_FOLDER'], get_filepath(game, version))


@app.route('/finished_upload/<game>/<version>', methods=['GET'])
def finished_upload(game: str, version: str):
    url = url_for('download_file', game=game, version=version)
    return f'''
    <!doctype html>
    <title>Finished upload for {game}:{version} build</title>
    <h1>Finished upload {game}:{version} build</h1>
    Share this link: <a href="{url}">{url}</a>
    '''

@app.route('/', methods=['GET'])
def root():
    return '''
    <!doctype html>
    <title>Bad URL</title>
    <h1>Bad URL</h1>
    '''

def main():
    app.run()

if __name__ == "__main__":
    main()
