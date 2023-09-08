from setuptools import setup, find_packages

setup(
    name='Chrom History Exporter',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'pandas',
        'openpyxl'
    ],
    entry_points={
        'console_scripts': [
            'histexport=histexport.histexport:main',
        ],
    },
)
