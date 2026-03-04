from collections import deque
import numpy as np

class ColeKripkeDetector:

    def __init__(self):
        self.activity_window = deque(maxlen=7)
        self.weights = np.array([
            0.0033,
            0.0090,
            0.0140,
            0.0170,
            0.0170,
            0.0140,
            0.0090
        ])

    def update(self, step_increment):
        self.activity_window.append(step_increment)

        #wait 7 mins
        if len(self.activity_window) != len(self.weights):
            return None

        activityArray = np.array(self.activity_window)

        score = np.dot(activityArray, self.weights)

        return 1 if score < 1 else 0