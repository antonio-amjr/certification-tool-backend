from .test_observer import Observable,Observer

class TestResultObservable(Observable):
    def __init__(self):
        self.observers = []

    def subscribe(self, observer):
        self.observers.append(observer)

    def unsubscribe(self, observer):
        self.observers.remove(observer)

    def notify(self, record):
        for observer in self.observers:
            observer.dispatch(record)
