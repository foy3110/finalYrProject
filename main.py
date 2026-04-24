from fastapi import FastAPI

from analysis.Analysis import dailySummary
from analysis.RollingBaseLine import rollingBaseLine, calculate_stress_score, run_analysis
from analysis.sleepDetector import *
app = FastAPI()