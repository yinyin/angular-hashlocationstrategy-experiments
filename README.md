# TL;DR

This experiment is subject to explore the way to have host page (ie: `index.html`) and other static files (`main.*.js`, `polyfills.*.js`, `asset/*`, ... etc.) serving from different paths.

The `experiments/` folder contains Angular projects with routing implemented with different combination of location strategy and `APP_BASE_HREF`.

A simple HTTP server (`httpdsim.py`) is implemented to serving `index.html` and other static files in different paths (`/my/app` vs. `/static-content/my-app-s/data/ui-file/`). This script needs Python 2.7 to run.

A bash script (`do-test.sh`) is written to build front-end bundles (ie: `ng build`) and serve with the HTTP server for each experiments.

# The experiment

The experiment project consists 2 components:

* Apples - routing path: `fruit/some-apples`
* Bicycle - routing path: `transport/bicycle`

Both component display a picture from `asset/` folder.

Routing is implemented with the following combinations:

| Branch                         | Location strategy  | w/ `APP_BASE_HREF` (set to `/my/app`)  | Description    |
|--------------------------------|--------------------|----------------------------------------|----------------|
| master (path-wo-app-base-href) | Path               | No     | PathLocationStrategy (w/o `APP_BASE_HREF`)  |
| path-w-app-base-href           | Path               | Yes    | PathLocationStrategy (w/ `APP_BASE_HREF`)   |
| hash-wo-app-base-href          | Hash               | No     | HashLocationStrategy (w/o `APP_BASE_HREF`)  |
| hash-w-app-base-href           | Hash               | Yes    | HashLocationStrategy (w/ `APP_BASE_HREF`)   |
| hash-w-empty-app-base-href     | Hash               | Yes    | HashLocationStrategy (w/ empty `APP_BASE_HREF`)  |
| proposehash-wo-app-base-href   | Hash (modified)    | No     | Purposed HashLocationStrategy (w/o `APP_BASE_HREF`)  |
| proposehash-w-app-base-href    | Hash (modified)    | Yes    | Purposed HashLocationStrategy (w/ `APP_BASE_HREF`)   |
| proposehash-w-empty-app-base-href | Hash (modified) | Yes    | Purposed HashLocationStrategy (w/ empty `APP_BASE_HREF`) |

A simple HTTP server (`httpdsim.py`) is implemented for simulating the deployment environment of web framework. The listening port can be specify by `--port` option. Assuming the server is started at http://127.0.0.1:8000/:

* The host page (`index.html`) will be serving at http://127.0.0.1:8000/my/app/.
* Other static files (`main.*.js`, `polyfills.*.js`, `asset/*`, ... etc.) will be serving at http://127.0.0.1:8000/static-content/my-app-s/data/ui-file/.

The server will rewrite the path of `base-href` tag to `/static-content/my-app-s/data/ui-file/` by default for convenient. The rewritten behavior can be disable by `--no-rewrite` option.

The expected routed URL for component for each location strategy is (use `Apples` component as sample):

* With path location strategy: http://127.0.0.1:8000/my/app/fruit/some-apples.
* With hash location strategy: http://127.0.0.1:8000/my/app#/fruit/some-apples.

# Result

The experiment is conduct with the following step:

1. Run `do-test.sh` in terminal. The script will build all experiments and start HTTP server for each experiment one-by-one.
2. Open experiment page in browser.
3. Switching to `Bicycle` component by clicking on `Bicycle` link.
4. Switching to `Apples` component by clicking on `Apples` link.
5. Record routed URL from address bar of browser.
6. Record the asset image is successfully loaded for display or not.
7. Open the routed URL in another browser or new browser tab. Record if the routed URL can be use in new browser session or not.
8. Back to terminal. Press CTRL-C for next experiment (Go to step 2).

The run-time environment for generating the following result is:

* Angular 7.0.2 (CLI 7.0.4)
* Node.js 10.13.0
* Python 2.7 (for HTTP server)

## Build method 1

The application is built with `ng build --prod` and `base-href` is rewritten to `/static-content/my-app-s/data/ui-file/` by the back-end. (This is equivalent to build with `ng build --prod --base-href=/static-content/my-app-s/data/ui-file/` and serving with `base-href` rewritten disabled).

| Branch                         | Location strategy  | w/ `APP_BASE_HREF` (set to `/my/app`)  | Routed URL for component   | Asset loaded ? | Revisit through Routed URL    |
|--------------------------------|--------------------|----------------------------------------|----------------------------|----------------|--------------------------------|
| master                         | Path               | No     | http://127.0.0.1:8001/static-content/my-app-s/data/ui-file/fruit/some-apples (not meeting expected URL) | Success | Failed (note-1) |
| path-w-app-base-href           | Path               | Yes    | http://127.0.0.1:8002/my/app/fruit/some-apples | Success | Failed (note-2) |
| hash-wo-app-base-href          | Hash               | No     | http://127.0.0.1:8003/static-content/my-app-s/data/ui-file/#/fruit/some-apples (not meeting expected URL) | Success | Failed (note-3) |
| hash-w-app-base-href           | Hash               | Yes    | http://127.0.0.1:8004/static-content/my-app-s/data/ui-file/#/my/app/fruit/some-apples (not meeting expected URL) | Success | Failed (note-3) |
| hash-w-empty-app-base-href     | Hash               | Yes    | http://127.0.0.1:8000/static-content/my-app-s/data/ui-file/#/fruit/some-apples (not meeting expected URL) | Success | Failed (note-3) |
| proposehash-wo-app-base-href   | Hash (modified)    | No     | http://127.0.0.1:8005/static-content/my-app-s/data/ui-file/#/fruit/some-apples (not meeting expected URL) | Success | Failed (note-3) |
| proposehash-w-app-base-href    | Hash (modified)    | Yes    | http://127.0.0.1:8000/my/app#/fruit/some-apples | Success | Success |
| proposehash-w-empy-app-base-href | Hash (modified)  | Yes    | http://127.0.0.1:8000/static-content/my-app-s/data/ui-file/#/fruit/some-apples (not meeting expected URL) | Success | Failed (note-3) |

* **note-1**: reject by static content handler - file not found (`${static_folder}/fruit/some-apples`)
* **note-2**: reject by server-side URL routing - no route for `/my/app/fruit/some-apples`.
* **note-3**: reject by static content handler - file not found (`${static_folder}/`)

## Build method 2

The application is built with `ng build --prod --base-href=/my/app/ --deploy-url=/static-content/my-app-s/data/ui-file/`.

The back-end `base-href` rewritten is disabled.

| Branch                         | Location strategy  | w/ `APP_BASE_HREF` (set to `/my/app`)  | Routed URL for component   | Asset loaded ? | Revisit through Routed URL    |
|--------------------------------|--------------------|----------------------------------------|----------------------------|----------------|--------------------------------|
| master                         | Path               | No     | http://127.0.0.1:8007/my/app/fruit/some-apples | Failed (note-4) | Failed (note-5) |
| path-w-app-base-href           | Path               | Yes    | http://127.0.0.1:8008/my/app/fruit/some-apples | Failed (note-6) | Failed (note-5) |
| hash-wo-app-base-href          | Hash               | No     | http://127.0.0.1:8009/my/app/#/fruit/some-apples | Failed (note-7) | Success (note-8) |
| hash-w-app-base-href           | Hash               | Yes    | http://127.0.0.1:8010/my/app/#/my/app/fruit/some-apples (not meeting expected URL) | Failed (note-9) | Success (note-8) |
| proposehash-wo-app-base-href   | Hash (modified)    | No     | http://127.0.0.1:8011/my/app/#/fruit/some-apples | Failed (note-10) | Success (note-8) |
| proposehash-w-app-base-href    | Hash (modified)    | Yes    | http://127.0.0.1:8012/my/app#/fruit/some-apples | Failed (note-11) | Success (note-8) |

* **note-4**: attempt to load asset through http://127.0.0.1:8007/my/app/assets/in-asset/apples.jpg and rejected by server-side URL routing.
* **note-5**: reject by server-side URL routing - no route for `/my/app/fruit/some-apples`.
* **note-6**: as same as note-4 (http://127.0.0.1:8008/my/app/assets/in-asset/apples.jpg).
* **note-7**: as same as note-4 (http://127.0.0.1:8009/my/app/assets/in-asset/apples.jpg).
* **note-8**: asset failed to load.
* **note-9**: as same as note-4 (http://127.0.0.1:8010/my/app/assets/in-asset/apples.jpg).
* **note-10**: as same as note-4 (http://127.0.0.1:8011/my/app/assets/in-asset/apples.jpg).
* **note-11**: as same as note-4 (http://127.0.0.1:8012/my/app/assets/in-asset/apples.jpg).
