"""
Helper functions to track QCD axion parameter space and model-dependent things.
"""

from .constants import *
from .fmath import *


# DFSZ and KSVZ parameter relations from 2003.01600



def Cae(ma, tanbeta, dfsz_type):  # ma in eV
    alpha = 1/137
    fa = 5.7e6 / ma
    if dfsz_type == "DFSZI":
        EbyN = 8/3
        return -(1/3)*sin(arctan(tanbeta))**2 + (3*alpha**2)/(4*pi**2) * (EbyN * log(fa/(0.511e-3)) - 1.92 * log(1/(0.511e-3)))
    if dfsz_type == "DFSZII":
        EbyN = 2/3
        return (1/3)*cos(arctan(tanbeta))**2 + (3*alpha**2)/(4*pi**2) * (EbyN * log(fa/(0.511e-3)) - 1.92 * log(1/(0.511e-3)))




def gae_DFSZ(ma, tanbeta, dfsz_type):  # ma in eV
    # return g_ae as a function of m_a, \tan\beta, and the DFSZ model (I or II)
    return abs(1.8e-7 * (0.511e-3) * ma * Cae(ma, tanbeta, dfsz_type))




def gagamma_KSVZ(ma, eByN):
    # return g_{a\gamma} as a function of m_a and E/N for the KSVZ models
    # ma in eV
    return (0.203*eByN - 0.39)*ma*1e-9




def gagamma_DFSZI(ma):
    return (0.203*8/3 - 0.39)*ma*1e-9




def gagamma_DFSZII(ma):
    return (0.203*2/3 - 0.39)*ma*1e-9