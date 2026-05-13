from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in packing_list_reports_fepl/__init__.py
from packing_list_reports_fepl import __version__ as version

setup(
	name="packing_list_reports_fepl",
	version=version,
	description="Packing List and Reports for FEPL",
	author="NexGen ERP Technologies",
	author_email="admin@example.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires,
)
