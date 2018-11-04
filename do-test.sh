#!/bin/bash

EXPERIMENTS=( 'path-wo-app-base-href' 'path-w-app-base-href' 'hash-wo-app-base-href' 'hash-w-app-base-href' 'proposehash-wo-app-base-href' 'proposehash-w-app-base-href' )

set -e
for experiment in "${EXPERIMENTS[@]}"; do
	echo "*** preparing experiment ${experiment}"
	cd experiments/${experiment}/
	if [ ! -f '.gitignore' ]; then
		echo "cannot reach file of experiment ${experiment}. check out submodule ?"
		continue
	fi
	if [ ! -d 'node_modules' ]; then
		npm i .
		git checkout -- package-lock.json
	fi
	ng build --prod
	cd ../..
done
set +e

portbase=8000

for experiment in "${EXPERIMENTS[@]}"; do
	httpdport=$(( portbase + 1 ))
	echo "*** activating http at port ${httpdport} for experiment ${experiment}."
	echo "*** open http://127.0.0.1:${httpdport}/my/app to view the experiment."
	echo "*** press Ctrl+C to finish this experiment."
	python2 httpdsim.py --port=${httpdport} experiments/${experiment}/dist/angular-hashlocationstrategy-experiment-x
	portbase=${httpdport}
done

set -e
for experiment in "${EXPERIMENTS[@]}"; do
	echo "*** preparing experiment ${experiment} with base-href and deploy-url embedded."
	cd experiments/${experiment}/
	if [ ! -f '.gitignore' ]; then
		echo "cannot reach file of experiment ${experiment}. check out submodule ?"
		continue
	fi
	ng build --prod --base-href=/my/app/ --deploy-url=/static-content/my-app-s/data/ui-file/
	cd ../..
done
set +e

for experiment in "${EXPERIMENTS[@]}"; do
	httpdport=$(( portbase + 1 ))
	echo "*** activating http at port ${httpdport} for experiment ${experiment} (with base-href and deploy-url embedded)."
	echo "*** open http://127.0.0.1:${httpdport}/my/app to view the experiment."
	echo "*** press Ctrl+C to finish this experiment."
	python2 httpdsim.py --port=${httpdport} --no-rewrite experiments/${experiment}/dist/angular-hashlocationstrategy-experiment-x
	portbase=${httpdport}
done

echo "*** all experiments completed."
