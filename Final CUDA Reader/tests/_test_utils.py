try:
    from IPython.display import display, clear_output
except ImportError:
    display = lambda x: print(x,end="\r")
    clear_output = lambda wait: None


class TestLogger():
    @staticmethod
    def cleanprint(msg):
        clear_output(wait=True)
        display(msg)
    info=debug=error= lambda self,x:self.cleanprint(x)