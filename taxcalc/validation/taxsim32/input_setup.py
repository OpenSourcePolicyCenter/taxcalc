"""
Generates TAXSIM-32 `.in` input files and downloads `.in.out-taxsim` output files
"""
import pandas as pd
import os, glob
from zipfile import ZipFile
# requires curl

def get_inputs():
    """
    Runs taxsim_input.py for all combinations of year and assumption sets
    """
    letters = ['a', 'b', 'c']
    years = ['2017', '2018']

    name_list = [str(y + ' ' + x) for x in letters for y in years]

    for name in name_list:
        command = str('python taxsim_input.py ' + name)
        os.system(command)


def get_ftp_output():
    """
    Uses `curl` to upload assumption set input files and save taxsim-32 output files
    """
    letters = ['a', 'b', 'c']
    years = ['17', '18']
    file_list = [str(x+y + '.in') for x in letters for y in years]


    for f in file_list:
        file_out = f + '.out-taxsim'
        os.system(f'curl -u taxsim:02138 -T {f} ftp://taxsimftp.nber.org/tmp/userid')
        os.system(f'curl -u taxsim:02138 ftp://taxsimftp.nber.org/tmp/userid.txm32 -o {file_out}')



if __name__ == '__main__':
    get_inputs()
    get_ftp_output()
