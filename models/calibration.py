from sklearn.calibration import CalibratedClassifierCV


def calibrate_model(model, X_train=None, y_train=None, method="isotonic", cv=3):
    calibrated = CalibratedClassifierCV(model, method=method, cv=cv)
    if X_train is not None and y_train is not None:
        calibrated.fit(X_train, y_train)
    return calibrated
