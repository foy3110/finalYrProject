from analysis.Analysis import dailySummary
from analysis.RollingBaseLine import rollingBaseLine, calculate_stress_score, run_analysis
from analysis.sleepDetector import *
x = dailySummary()
print(x)
run_analysis()
