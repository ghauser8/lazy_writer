import os
import math


'''
Lazy LP writer: use generators to write extremely large .lp files to disk.

Highest level task (lazy_writer): actually write the contents of an arbitrary 
    generator to a disk.

A subtask: create a "generator generator" that will create a user-defined 
    generator on demand. User passes an index, an iterable compatible with the 
    specified index, and a str literal to represent the variable of iterest.

DESIRED USAGE:

m = lazy_writer.Model()
m.add_variable(name='x', default_index = (i for i in range(4)))
m.add_constraints(sum('x', data, 'i for i in range(len(data))') <= 50)
m.add_variable('x', default_index)
m.add_constraints(sum(m.x, coefficients, index) + sum(m.x, coefficients) <= 
    rhs[j], constraint_index)
'''





class Model:
    def __init__(self):
        self.variables = {}
        self.objective = None
        self.constraints = {}

    # user has to pass default_index = lambda: (gener) for this
    # to work.
    def add_variable(self, name, variable_type, default_index):
        self.variables[name] = {'variable_type': variable_type,
                                'default_index': default_index} 

    class Variable:
        def __init__(self, name, variable_type, default_index = None):
            self.name = name
            self.type = variable_type
            self.default_index = default_index
           
        
        def sum(self, coefficients = None, index = None):
            '''
            coefficients (list | dict): container for coefficients, indexed 
                safely on index or self.default_index
                
            index (iterable): desired summation index; should be a subset of
                self.default_index but that is not enforced.

            DESCRIPTION: return a generator for writing a sum of the variable
            '''
            if index is None and self.default_index is None:
                print(f'No default_index for {self.name}; \
                        please pass an index')
                raise ValueError

            if coefficients is None:
                return (f'{self.name}{i}' + ' + \n' for i in index)    
            
            return (f'{coefficients[i]} {self.name}{i}' + ' + \n' 
                    for i in index) 



def dot(a, x, index):
    '''
    a (non-generator iterable): coefficients in any data structure that allows 
        a[i] for i in index
    x (str lit): string representation of the variable of interest
    index (iterable): sequence over which to perform dot product of a dot x

    DESCRIPTION: return a generator that can be used to write the dot product 
        of a and x, where a is some iterable and x is a string rep of a 
        variable.
    '''

    # this does a thing: the values in the sequence index + the value of x 
    #   determines the naming convention of x implicitly.
    # I think I like this behavior.

    # this needs some error handling 
    #   (for example a[i] must be a numerical for all i)
    # i in index should be auto-stripped of whitespace and _
    # handle operator appending appropriately (leads non first elements only)
    return (f'{a[i]} {x}_{i} + ' for i in index)

def generator_genr(index, data, var_str):
    '''
    index (str lit.): str representation of the rule that will generate desired 
        index. E.g., "for i in range(5)".
    '''
    return eval(f'({index})')

def write_constr():
    pass


def lazy_writer(fn, genr):
    '''
    fn (str): target filename. will be overwritten if already exists

    DESCRIPTION: A script to explore how to use generators to write massive 
        files (contents larger than available RAM).
    '''

    if genr is None:
        # some default behavior for testing
        genr = (f'{i}_blah ' for i in range(math.factorial(12)))


    with open(fn, 'w') as f:
        line = []
        line_length = 0
        while True:
            try:
                next_word = next(genr)
                line_length += len(next_word)
                if line_length <= 255:
                    # with next_word, we're still beneath the line limit; so add
                    #   next_word.
                    line.append(next_word)
                else:
                    # with next_word, we're over the limit. FIRST write curernt
                    #   line, THEN reset line with next_word and reset 
                    #   line_length
                    f.write(''.join(line + ['\n']))
                    line = [next_word]
                    line_length = len(next_word)
            except StopIteration:
                # generator has been exhausted; time to go home.
                break
        if len(line) > 0:    
            # make sure to write any dangling data
            f.write(''.join(line + ['\n']))

    print(f'All done! Your file is here: {os.path.join(os.getcwd(),fn)}')


if __name__ == '__main__':
    lazy_writer('BigBlah.txt')
