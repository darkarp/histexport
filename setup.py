from setuptools import setup, find_packages

# Read the long description from README.md
with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

# Define package metadata
metadata = {
    'name': 'histexport',
    'version': '0.2.3',
    'description': 'A Python utility to export Chromium-based browser history and downloads to various formats.',
    'author': 'Mario Nascimento',
    'author_email': 'mario@whitehathacking.tech',
    'url': 'https://github.com/darkarp/histexport',
    'license': 'MIT',
    'keywords': ['history', 'browser', 'chromium', 'export', 'downloads', 'URLs'],
    'classifiers': [
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Developers',
        'Topic :: Security',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
}

# Define package requirements
requirements = [
    'pandas >= 1.0.0',
    'openpyxl >= 3.0.0',
]

# Entry points for command line utility
entry_points = {
    'console_scripts': [
        'histexport=histexport.histexport:main',
    ],
}

# Setup
setup(
    **metadata,
    packages=find_packages(exclude=["tests*"]),
    install_requires=requirements,
    long_description=long_description,
    long_description_content_type='text/markdown',
    entry_points=entry_points,
    python_requires='>=3.7',
    include_package_data=True,  # Will include any non-python files specified in MANIFEST.in
)
