class Bijection(dict):
    """ This class defines a bijection object based on dict

    It can be used exactly like dict, but additionally has a property
    'inverse' which contains the inverted {value: key} dict. """
    def __init__(self, *args, **kwargs):
        super(Bijection,self).__init__(*args,**kwargs)
        self.inverse = {v: k for k, v in self.items()}
        
    def __setitem__(self,key,value):
        super(Bijection,self).__setitem__(key,value)
        self.inverse[value]=key
    
    def __delitem__(self, key):
        self.inverse.__delitem__(self.__getitem__(key))
        super(Bijection,self).__delitem__(key)
        
    def pop(self, key):
        self.inverse.pop(self.__getitem__(key))
        super(Bijection,self).pop(key)
        
    def update(self,*args, **kwargs):
        super(Bijection,self).update(*args,**kwargs)
        self.inverse = {v: k for k, v in self.items()}
        