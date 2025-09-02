import os
from flask import Flask, flash, request, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
from functools import wraps
import sys
from multiprocessing import Process

UPLOAD_FOLDER = '/datas'
with open('./static/upload.html') as f:
    UPLOAD_HTML_CONTENT = f.read()
UPLOAD_CHUNK_SIZE = 1 * 1024 * 1024 # 1MB

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['UPLOAD_HTML_CONTENT'] = UPLOAD_HTML_CONTENT
app.config['UPLOAD_CHUNK_SIZE'] = UPLOAD_CHUNK_SIZE

def login_required(f):
    def check_auth(username, password):
        if username == os.getenv('ADMIN_USERNAME', None):
            if password == os.getenv('ADMIN_PASSWORD', None):
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

def get_filepath_chunk_root(game: str, version: str) -> tuple[str, str]:
    return get_filepath(game, version) + '_chunk_', '.part'

def get_filepath_chunk(game: str, version: str, chunk: int) -> str:
    a, b = get_filepath_chunk_root(game, version)
    return a + f'{chunk}' + b

def get_upload_html_content(game: str, version: str, auth_header: str, upload_chunk_size: int) -> str:
    content = app.config['UPLOAD_HTML_CONTENT']
    assert isinstance(content, str)
    return (
        content
            .replace('${game}', game)
            .replace('${version}', version)
            .replace('${auth_header}', auth_header)
            .replace('${upload_chunk_size}', str(upload_chunk_size))
    )

def clean_old_upload_chunk(game: str, version: str):
    print("LOG: clean_old_upload_chunk start...", file=sys.stderr)
    root_file_prefix, root_file_sufix = get_filepath_chunk_root(game, version)
    for file in os.listdir(app.config['UPLOAD_FOLDER']):
        assert isinstance(file, str)
        if file.startswith(root_file_prefix) and file.endswith(root_file_sufix):
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file))
    print("LOG: clean_old_upload_chunk end...", file=sys.stderr)

def assemble_upload_chunk(game: str, version: str, file_max_chunk: int):
    print("LOG: assemble_upload_chunk start...", file=sys.stderr)
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], get_filepath(game, version))
    with open(full_path, 'wb') as f_dest:
        for i in range(file_max_chunk):
            full_path_chunk = os.path.join(app.config['UPLOAD_FOLDER'], get_filepath_chunk(game, version, i))
            if not os.path.isfile(full_path_chunk):
                return "failed to get all chunk data", 500
            with open(full_path_chunk, 'rb') as f_chunk:
                while chunk := f_chunk.read(1024):
                    _ = f_dest.write(chunk)
            os.remove(full_path_chunk)
    print("LOG: assemble_upload_chunk end...", file=sys.stderr)

@app.route('/upload-chunk/<game>/<version>', methods=['POST'])
@login_required
def upload_file_chunk(game: str, version: str):
    def get_value(header_name: str) -> int | tuple[str, int]:
        v = request.headers.get(header_name, None)
        if v is None or not v.isnumeric():
            return (f'{header_name} not set', 400)
        return int(v)
    if 'file' not in request.files:
        return ('No file part', 400)
    file = request.files['file']
    if file.filename == '' or file.filename is None:
        return ('No selected file', 400)
    file_size = get_value('filesizecustom')
    if not isinstance(file_size, int):
        return file_size
    file_max_chunk = get_value('filemaxchunkcustom')
    if not isinstance(file_max_chunk, int):
        return file_max_chunk
    file_chunk = get_value('filechunkcustom')
    if not isinstance(file_chunk, int):
        return file_chunk
    if file_chunk == 0:
        clean_old_upload_chunk(game, version)
    full_path_chunk = os.path.join(app.config['UPLOAD_FOLDER'], get_filepath_chunk(game, version, file_chunk))
    os.makedirs(os.path.dirname(full_path_chunk), exist_ok=True)
    with open(full_path_chunk, 'wb') as f:
        for chunk in file.stream:
            _ = f.write(chunk)
    if file_chunk >= file_max_chunk - 1:
        p = Process(target=assemble_upload_chunk, args=(game, version, file_max_chunk), daemon=True)
        p.start()
        #_ = assemble_upload_chunk(game, version, file_max_chunk)
        return redirect(url_for('finished_upload', game=game, version=version))
    return f"Chunk {file_chunk} on {file_max_chunk} uploaded.", 200


@app.route('/upload/<game>/<version>', methods=['GET'])
@login_required
def upload_file(game: str, version: str):
    auth_header = request.headers.get('authorization')
    if auth_header is None:
        flash('Bad auth header')
        return redirect(url_for('upload', game=game, version=version))
    return get_upload_html_content(game, version, auth_header, app.config['UPLOAD_CHUNK_SIZE'])


@app.route('/download/<game>/<version>', methods=['GET'])
def download_file(game: str, version: str):
    return send_from_directory(app.config['UPLOAD_FOLDER'], get_filepath(game, version))


@app.route('/finished_upload/<game>/<version>', methods=['GET'])
def finished_upload(game: str, version: str):
    url = url_for('download_file', game=game, version=version)
    return f'''
    <!doctype html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Finished upload for {game}:{version} build</title>
    </head>
    <body>
        <h1>Finished upload {game}:{version} build</h1>
        <p>Share this link: <a href="{url}">{url}</a></p>
        <p>The file will be available in a few minutes</p>
    </body>
    </html>
    '''

@app.route('/', methods=['GET'])
def root():
    return "Bad Request", 400

def main():
    app.run()

if __name__ == "__main__":
    main()
