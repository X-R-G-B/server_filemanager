module main

import veb
import os
import encoding.base64

pub struct Context {
	veb.Context
}

pub struct App {
	upload_folder string = '/datas'
	upload_file string = $embed_file('./static/upload.html').to_string()
}

fn main() {
	mut app := &App{}

	veb.run[App, Context](mut app, 8080)
}

fn get_upload_file(upload_file string, game string, version string, auth_header string) string {
	return upload_file.replace_each([r'${game}', game, r'${version}', version, r'${auth_header}', auth_header])
}

fn is_auth_admin(auth_header string) bool {
	admin_value_username := os.getenv_opt('ADMIN_USERNAME') or {
		eprintln('Error: ADMIN_USERNAME env variable not set')
		return false
	}
	admin_value_password := os.getenv_opt('ADMIN_PASSWORD') or {
		eprintln('Error: ADMIN_PASSWORD env variable not set')
		return false
	}
	admin_value := 'Basic ' + base64.encode_str(admin_value_username + ':' + admin_value_password)
	return auth_header == admin_value
}

fn get_filepath(game string, version string) string {
	return '${game}_${version}'.replace_each(['.', '']) + '.zip'
}

fn get_filepath_chunk(game string, version string, chunk u64) string {
	return get_filepath(game, version) + '_chunk_${chunk}.part'
}

fn get_header_u64(ctx Context, header string) !u64 {
	header_string := ctx.get_custom_header(header) or {
		return error('"${header}" was not set')
	}
	header_u64 := header_string.u64()
	return header_u64
}

@['/upload-chunk/:game/:version'; post]
pub fn (app &App) upload_game_version_chunk(mut ctx Context, game string, version string) veb.Result {
	auth_header := ctx.get_header(.authorization) or {
		ctx.set_custom_header('WWW-Authenticate', 'Basic realm="Login Required"') or {
			return ctx.server_error('Bad authorization')
		}
		return ctx.server_error_with_status(.unauthorized)
	}
	if !is_auth_admin(auth_header) {
		return ctx.server_error_with_status(.unauthorized)
	}
	if 'file' !in ctx.files {
		return ctx.server_error('"file" was not sent')
	}
	file_size := get_header_u64(ctx, 'filesizecustom') or {
		return ctx.server_error(err.msg())
	}
	file_max_chunk := get_header_u64(ctx, 'filemaxchunkcustom') or {
		return ctx.server_error(err.msg())
	}
	file_chunk := get_header_u64(ctx, 'filechunkcustom') or {
		return ctx.server_error(err.msg())
	}
	full_path_chunk := os.join_path(app.upload_folder, get_filepath_chunk(game, version, file_chunk))
	os.rm(full_path_chunk) or {}
	mut f_chunk := os.create(full_path_chunk) or {
		eprintln('Error: ${err}')
		return ctx.server_error('Error when saving file')
	}
	unsafe {
		f_chunk.write_full_buffer(ctx.files['file'].data, file_size) or {
			eprintln('Error: ${err}')
			f_chunk.close()
			return ctx.server_error('Error when saving file')
		}
	}
	f_chunk.close()
	if file_chunk >= file_max_chunk - 1 {
		full_path := os.join_path(app.upload_folder, get_filepath_chunk(game, version, file_chunk))
		os.rm(full_path) or {}
		mut f_final := os.create(full_path) or {
			eprintln('Can"t create file ${full_path}')
			return ctx.server_error('Error when saving file')
		}
		for i in 0 .. file_max_chunk {
			full_path_tmp_chunk := get_filepath_chunk(game, version, i)
			f_tmp_bytes := os.read_bytes(full_path_tmp_chunk) or {
				eprintln('Can"t open file tmp chunk ${full_path_tmp_chunk}')
				f_final.close()
				return ctx.server_error('Error when saving file')
			}
			f_final.write(f_tmp_bytes) or {
				eprintln('Can"t write bytes from ${full_path_tmp_chunk} to ${full_path}')
				f_final.close()
				return ctx.server_error('Error when saving file')
			}
		}
		f_final.close()
		return ctx.redirect('/finished/${game}/${version}', typ: .see_other)
	}
	return ctx.text('')
}

@['/upload/:game/:version'; get]
pub fn (app &App) upload_game_version(mut ctx Context, game string, version string) veb.Result {
	auth_header := ctx.get_header(.authorization) or {
		ctx.set_custom_header('WWW-Authenticate', 'Basic realm="Login Required"') or {
			return ctx.server_error('Bad authorization')
		}
		return ctx.server_error_with_status(.unauthorized)
	}
	if !is_auth_admin(auth_header) {
		return ctx.server_error_with_status(.unauthorized)
	}
	return ctx.html(get_upload_file(app.upload_file, game, version, auth_header))
}

@['/finished/:game/:version'; get]
pub fn (app &App) finished_game_version(mut ctx Context, game string, version string) veb.Result {
	url := '/download/${game}/${version}'
	return ctx.html('
	<!doctype html>
	<html>
	<head>
		<meta charset="UTF-8">
		<title>Finished upload for ${game}:${version} build</title>
	</head>
	<body>
		<h1>Finished upload ${game}:${version} build</h1>
		<p>Share this link: <a href="${url}">${url}</a></p>
	</body>
	</html>
	')
}

@['/download/:game/:version'; get]
pub fn (app &App) download_game_version(mut ctx Context, game string, version string) veb.Result {
	full_path := os.join_path(app.upload_folder, get_filepath(game, version))
	return ctx.file(full_path)
}
