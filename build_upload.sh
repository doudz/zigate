rm -R build
rm -R dist
python3 setup.py sdist
twine upload dist/*
