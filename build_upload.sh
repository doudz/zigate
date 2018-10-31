rm -R build
rm -R dist
python3 setup.py sdist bdist_wheel
twine upload dist/*
