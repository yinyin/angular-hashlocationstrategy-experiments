#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
A test HTTP server for experimenting serving host page and other static
contents from different URL

The host page (index.html) is serving at /my/app.
Other static files are serving under /static-content/my-app-s/data/ui-file/.

The <base href=""> tag will be rewrite on fly for referencing assets.
"""

import sys
import re
import time
import datetime
from string import whitespace
from os import stat as path_stat
from os.path import abspath
from os.path import isfile
from os.path import join as joinpath
from mimetypes import guess_type as mime_guess_type
from wsgiref.simple_server import make_server
from wsgiref.util import shift_path_info
import getopt
import logging

_log = logging.getLogger(__name__)

# Library (commonutil.net.wsgi)

_PATH_STRIP_CHARACTERS = "/" + whitespace

_TEXT_WEEKDAY = (
		"Mon",
		"Tue",
		"Wed",
		"Thu",
		"Fri",
		"Sat",
		"Sun",
)
_TEXT_MONTH = (
		"Jan",
		"Feb",
		"Mar",
		"Apr",
		"May",
		"Jun",
		"Jul",
		"Aug",
		"Sep",
		"Oct",
		"Nov",
		"Dec",
)


def httpdate_from_datetime(dt):
	# type: (datetime.datetime) -> str
	"""
	Return a string representation of given datetime.datetime object according to RFC 1123 (HTTP/1.1).
	The supplied datetime object must be in UTC.

	Args:
		dt: datetime.datetime object of required date

	Return:
		HTTP date string
	"""
	return "%s, %02d %s %04d %02d:%02d:%02d GMT" % (
			_TEXT_WEEKDAY[dt.weekday()],
			dt.day,
			_TEXT_MONTH[dt.month - 1],
			dt.year,
			dt.hour,
			dt.minute,
			dt.second,
	)


def httpdate_from_timestamp(tstamp):
	# type: (int) -> str
	"""
	Return a string representation of given epoch time-stamp according to RFC 1123 (HTTP/1.1).

	Args:
		dt: time-stamp of required date

	Return:
		HTTP date string
	"""
	dt = datetime.datetime.utcfromtimestamp(tstamp)
	return httpdate_from_datetime(dt)


_MONTH_KEYMAP = {
		"JAN": 1,
		"FEB": 2,
		"MAR": 3,
		"APR": 4,
		"MAY": 5,
		"JUN": 6,
		"JUL": 7,
		"AUG": 8,
		"SEP": 9,
		"OCT": 10,
		"NOV": 11,
		"DEC": 12,
}

_HTTPDATE_REGEX = re.compile(r"[A-Za-z]+,\s*([0-9]+)\s+([A-Za-z]+)\s+([0-9]+)\s+([0-9]+):([0-9]+):([0-9]+)\s+(GMT|UTC)")


def parse_httpdate(v):
	# type: (str) -> Optional[datetime.datetime]
	"""
	Parse HTTP date string into datetime.datetime object

	Args:
		v: String to parse

	Return:
		Return datetime.datetime object when parsing success, None otherwise.
	"""
	m = _HTTPDATE_REGEX.match(v)
	if m:
		try:
			day = int(m.group(1))
			month = _MONTH_KEYMAP[m.group(2).upper()]
			year = int(m.group(3))
			hour = int(m.group(4))
			minute = int(m.group(5))
			second = int(m.group(6))
			return datetime.datetime(year, month, day, hour, minute, second)
		except Exception:
			_log.exception("failed on parsing HTTP date text: %r", v)
	return None


HEADER_NO_CACHE = [
		("Cache-Control", "no-cache, must-revalidate"),  # HTTP/1.1
		("Expires", "Mon, 26 Jul 1997 05:00:00 GMT"),
		("Pragma", "no-cache"),
]  # Pragma: no-cache - HTTP/1.0, for elder proxies

HEADAR_MIME_TEXT = [
		("Content-Type", "text/plain"),
]


def make_expire_header(expire_seconds=600):
	# type: (int) -> List[Tuple[str, str]]
	"""
	Make header list for content expiration.

	Args:
		expire_seconds=600: Content expiration seconds

	Return:
		List of header content
	"""
	expire_tstamp = int(time.time()) + expire_seconds
	return [
			("Cache-Control", "private"),
			("Expires", httpdate_from_timestamp(expire_tstamp)),
			("Pragma", "no-cache"),
	]  # Pragma: no-cache - HTTP/1.0, for elder proxies


def fill_text_response(start_response, http_status, message_text=None):
	# type: (Callable[..., None], str, Optional[str]) -> Iterator[str]
	"""
	Return HTTP headers and plain text content body.

	Args:
		start_response: WSGI response callable
		http_status: HTTP status code
		message_text=None: Text content to place into content body

	Yield:
		Text body
	"""
	start_response(http_status, HEADER_NO_CACHE + HEADAR_MIME_TEXT)
	if message_text:
		yield message_text


def fill_response_403(start_response, message_text="Forbidden"):
	# type: (Callable[..., None], Optional[str]) -> Iterator[str]
	"""
	Return HTTP 403 Forbidden headers and text content body.

	Args:
		start_response: WSGI response callable
		message_text="Forbidden": Text content to place into content body

	Yield:
		Text body
	"""
	return fill_text_response(start_response, "403 Forbidden", message_text)


def fill_response_404(start_response, message_text="Not Found"):
	# type: (Callable[..., None], Optional[str]) -> Iterator[str]
	"""
	Return HTTP 404 Not Found headers and text content body.

	Args:
		start_response: WSGI response callable
		message_text="Not Found": Text content to place into content body

	Yield:
		Text body
	"""
	return fill_text_response(start_response, "404 Not Found", message_text)


def fill_response_304(start_response, etag, last_modify, expire_seconds=600, message_text="Not Modified"):
	# type: (Callable[..., None], str, datetime.datetime, int, int, Optional[str]) -> Iterator[str]
	"""
	Return HTTP 304 Not Modified headers and text content body.

	Args:
		start_response: WSGI response callable
		etag: Header content of HTTP ETag
		last_modify: Header content of HTTP Last-Modified
		expire_seconds=600: Content expiration seconds
		message_text="Not Modified": Text content to place into content body

	Yield:
		Text body
	"""
	start_response("304 Not Modified",
					make_expire_header(expire_seconds) + [
							("ETag", etag),
							("Last-Modified", last_modify),
					])
	if message_text:
		yield message_text


_EPOCH_DATETIME = datetime.datetime.utcfromtimestamp(0)


def _do_conditional_get(environ, start_response, etag, last_modify, modify_timestamp, acceptable_aging_sec=1):
	""" (internal) Perform conditional-get

	Return:
		Return output generator on conditional get.
		Return None when not conditional get operation.
	"""
	remote_etag = environ.get("HTTP_IF_NONE_MATCH", "")
	if remote_etag == etag:
		return fill_response_304(start_response, etag, last_modify)
	remote_last_modify = environ.get("HTTP_IF_MODIFIED_SINCE", "")
	if remote_last_modify == last_modify:
		return fill_response_304(start_response, etag, last_modify)
	if remote_last_modify:
		aux = parse_httpdate(remote_last_modify)
		if (aux is not None) and ((modify_timestamp - (aux - _EPOCH_DATETIME).total_seconds()) < acceptable_aging_sec):
			return fill_response_304(start_response, etag, last_modify)
	return None


class StaticFileHandler(object):
	"""
	提供靜態檔案的 WSGI handler

	WSGI handler offers static file serving
	"""

	def __init__(self, root_path, *args, **kwds):
		# type: (str) -> None
		""" (建構子 / Constructor)

		Args:
			root_path: 檔案資料夾的路徑，必須為絕對路徑 / Absolute path to file folder
		"""
		super(StaticFileHandler, self).__init__(*args, **kwds)
		self._root_path = root_path

	def __call__(self, environ, start_response, shifted_url_path=None):
		"""
		處理函數，當檔案路徑未給定時會由 PATH_INFO 環境變數中抓取。
		呼叫的函數可利用 `wsgiref.util.shift_path_info(environ)` 或是類似的函數預先調整 PATH_INFO 環境變數的內容。

		Handling callable. Will get file path from PATH_INFO environment variable.
		Caller can adjust content of PATH_INFO by `wsgiref.util.shift_path_info(environ)` or similar functions.

		Args:
			environ, start_response: WSGI 參數 / WSGI parameters
			shifted_url_path=None: 目標的檔案 URL 路徑 / URL path to target file
		"""
		if not shifted_url_path:
			shifted_url_path = environ.get("PATH_INFO", "")
		shifted_url_path = shifted_url_path.lstrip(_PATH_STRIP_CHARACTERS)
		file_path = abspath(joinpath(self._root_path, shifted_url_path))
		if not file_path.startswith(self._root_path):
			return fill_response_403(start_response)
		if not isfile(file_path):
			return fill_response_404(start_response)
		file_stat = path_stat(file_path)
		mtime = int(file_stat.st_mtime)
		last_modify = httpdate_from_timestamp(mtime)
		etag = "\"" + str(mtime) + "\""
		# {{{ conditional get
		aux = _do_conditional_get(environ, start_response, etag, last_modify, mtime)
		if aux:
			return aux
		# }}} conditional get
		mime_type, _content_encoding, = mime_guess_type(file_path)
		if not mime_type:
			mime_type = "application/octet-stream"
		start_response("200 OK",
						make_expire_header() + [
								("ETag", etag),
								("Last-Modified", last_modify),
								("Content-Type", mime_type),
								("Content-Length", str(file_stat.st_size)),
						])
		file_wrapper = environ.get("wsgi.file_wrapper")
		fp = open(file_path, "rb")
		if file_wrapper:
			return file_wrapper(fp, 4096)
		return iter(lambda: fp.read(4096), "")

	def __repr__(self, *_args, **_kwds):
		return "%s.StaticFileHandler(root_path=%r)" % (
				__name__,
				self._root_path,
		)


# Application

TRAP_BASEHREF = re.compile(r'<base\s+href\s*=\s*"([^"]*)"\s*/?\s*>', re.IGNORECASE)

STATIC_CONTENT_PATH = "/static-content/my-app-s/data/ui-file/"


def translate_host_page(file_path):
	with open(file_path, "r") as fp:
		for l in fp:
			m = TRAP_BASEHREF.search(l)
			if m:
				yield l[:m.start()] + "<base href=\"" + STATIC_CONTENT_PATH + "\">" + l[m.end():]
			else:
				yield l


def check_n_shift_path_prefix(environ, *args):
	for arg in args:
		n = shift_path_info(environ)
		if n != arg:
			return False
	return True


class HostpageStaticSeperatedLocation(object):
	def __init__(self, dist_folder_path, *args, **kwds):
		super(HostpageStaticSeperatedLocation, self).__init__(*args, **kwds)
		self._dist_folder_path = dist_folder_path
		self._static_content_handler = StaticFileHandler(dist_folder_path)

	def serv_host_page(self, environ, start_response):  # pylint: disable=unused-argument
		start_response('200 OK', HEADER_NO_CACHE + [
				("Content-Type", "text/html"),
		])
		return translate_host_page(joinpath(self._dist_folder_path, "index.html"))

	def serv_static_content(self, environ, start_response):
		path_info = environ.get("PATH_INFO", "/")
		if path_info in ("/", ""):
			return fill_response_404(start_response)
		return self._static_content_handler(environ, start_response, path_info)

	def __call__(self, environ, start_response):
		path_info = environ.get("PATH_INFO", "/")
		if path_info in ("/", ""):
			start_response('200 OK', HEADER_NO_CACHE + HEADAR_MIME_TEXT)
			return ("Visit /my/app instead.", )
		comp_name = shift_path_info(environ)
		if comp_name in ("my", "our"):
			if check_n_shift_path_prefix(environ, "app"):
				return self.serv_host_page(environ, start_response)
		elif comp_name == "static-content":
			if check_n_shift_path_prefix(environ, "my-app-s", "data", "ui-file"):
				return self.serv_static_content(environ, start_response)
		return fill_response_404(start_response)


_HELP_TEXT = """
Argument: [Options...] [DIST_FOLDER_PATH]

Options:
	-p [HTTP_PORT] | --port=[HTP_PORT]
		HTTP port number
	-H [HTTP_HOST] | --host=[HTP_HOST]
		HTTP host address
	-h | --help
		Help message

""".replace("\t", "    ")


def _parse_option(argv):
	http_host = "localhost"
	http_port = 8000
	dist_folder_path = None
	opts, args, = getopt.getopt(argv, "H:p:h", (
			"host=",
			"port=",
			"help",
	))
	for opt, arg, in opts:
		if opt in ("-p", "--port"):
			http_port = int(arg)
		elif opt in ("-H", "--host"):
			http_host = str(arg)
		elif opt in ("-h", "--help"):
			print _HELP_TEXT
			sys.exit(1)
	for arg in args:
		if dist_folder_path is not None:
			_log.warning("already specified dist folder path, will overwrite: %r (use %r instead)", dist_folder_path, arg)
		dist_folder_path = arg
	if not dist_folder_path:
		raise ValueError("required parameter DIST_FOLDER_PATH not given.")
	dist_folder_path = abspath(dist_folder_path)
	aux = joinpath(dist_folder_path, "index.html")
	if not isfile(aux):
		raise ValueError("cannot reach index.html: %r" % (aux, ))
	return (http_host, http_port, dist_folder_path)


def main():
	logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
	http_host, http_port, dist_folder_path = _parse_option(sys.argv[1:])
	_log.info("serving static content from: %r", dist_folder_path)
	webapp = HostpageStaticSeperatedLocation(dist_folder_path)
	httpd = make_server(http_host, http_port, webapp)
	try:
		_log.info("starting HTTP server at port %r", http_port)
		httpd.serve_forever()
	except KeyboardInterrupt:
		pass
	return 0


if __name__ == '__main__':
	sys.exit(main())
# <<< if __name__ == '__main__':

# vim: ts=4 sw=4 ai nowrap
