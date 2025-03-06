import os
import math
import types


'''
Lazy LP writer: use generators to write extremely large .lp files to disk.

Highest level task (lazy_writer): actually write the contents of an arbitrary 
    generator to a disk.

A subtask: create a "generator generator" that will create a user-defined 
    generator on demand. User passes an index, an iterable compatible with the 
    specified index, and a str literal to represent the variable of iterest.

DESIRED USAGE (something like):

m = lazy_writer.Model()

m.add_variable(name='x', default_index = lambda: (i for i in range(4)))

m.add_constraints(sum('x', data, 'i for i in range(len(data))') <= 50)

m.add_variable('x', default_index)

m.add_constraints(sum(m.x, coefficients, index) + sum(m.x, coefficients) <= 
    rhs[j], constraint_index)
'''

class Model:
    def __init__(self):
        self.variables = {}
        self.constraints = {}
        self.constraint_block = 0
        self.var_types = [
                'Real',
                'nonnegative_Real',
                'nonpositive_Real',
                'positive_Real',
                'negative_Real',
                'Integer',
                'nonnegative_Integer',
                'nonpositive_Integer',
                'positive_Integer',
                'negative_Integer',
                'Binary'
        ]
        self.expr_types = [str, 
                           types.FunctionType, 
                           types.LambdaType,
                           list]

    def check_expr(self, expr):
        if type(expr) not in self.expr_types:
            raise ValueError(f'Bad expression: {expr}')
         
    # user has to pass default_index = lambda: (gener) and you have to call it
    # like m.variables['x']['default_index']() for this to work.
    def add_variable(self, 
                     name, 
                     variable_type, 
                     upper_bounds = None,
                     lower_bounds = None,
                     default_index = None):
        '''
        name (str): user-defined variable name, e.g. 'x'
        variable_type (str): variable type, e.g. 'Binary'
        upper_bounds (iterable | float | int): upper bounds of variable. 
            If iterable, assumed to be indexed on default_index; if float or 
            int, the single bound value is applied to every index of the 
            variable
        lower_bounds (iterable | float | int): see upper_bounds
        default_index (lambda): (preferably) a generator wrapped in a lambda 
            function, e.g. lambda (i for i in my_data if i == my_condition)

        DESCRIPTION: record within the model object all of the information 
            required to use a variable easily when writing. everything in the 
            Model.variables dict is a callable (except for 'variable_type') 
            by way of lambdas; ideally, each lambda returns a generator as 
            defined by the user when defining the variable.
        '''
        # check for valid variable type
        if variable_type not in self.var_types:
            raise ValueError(f"Bad variable_type: {variable_type}")

        # If user passed a scalar for one of the bounds, transform it into a 
        #   lambda for them so that usage will be identical to the case where
        #   they pass a lw-generator.
        if type(upper_bounds) in [int, float]:
            upper_bounds = lambda: upper_bounds

        if type(lower_bounds) in [int, float]:
            lower_bounds = lambda: lower_bounds

        self.variables[name] = {'variable_type': variable_type,
                                'upper_bounds': upper_bounds,
                                'lower_bounds': lower_bounds,
                                'default_index': default_index} 
    
    def add_objective(self, expression, sense):
        '''
        expression (list of generators): the linear expression passed by the 
            user

        sense (str): min or max

        DESCRIPTION: store the expression passed by the user and prepare it for
            lazy writing. The form of expression is still TBD; likely accept 
            both a string literal and some kind of list of generators.
        '''
        # check that expression is either a string or a list of lambdas
        self.check_expr(expression)

        # check objective sense
        if sense not in ['MIN','MAX']:
            raise ValueError(f'Bad sense: {sense}')

        if type(expression) == list:
            self.objective_expr = expression
        else:
            self.objective_expr = [expression]

        self.objective_sense = sense

    def add_constraints(self, expression, sense, rhs, index, block_name = None):
        '''
        expression (list of lw-generators | str): linear expression passed by 
        the user

        sense (str): the sense of the constraint, e.g., '<=', '>=', '=='

        rhs (int | float | iterable): the right-hand-side of the constraint
            if iterable, must be indexable on `index`

        index (lambda function): a lw-generator defining
            the index to write the constraints against

        DESCRIPTION: store the rules to create the appropriate constraint block
        '''

        self.check_expr(expression)
        if not block_name:
            self.constraints[self.constraint_block] = (expression, sense, 
                                                       rhs, index)
            self.constraint_block += 1
        else:
            self.constraints[block_name] = (expression, sense, index)



    def sum(self, var, coefficients = None, index = None):
        '''
        var (str): string repr of var to sum; var in self.variables must be true

        coefficients (iterable): iterable object that is indexed on at least 
            index if not also var's default_index; passing None omits 
            coefficients altogether

        index (lambda): lw-generator defining the index to sum the 
            variable over instead of the variable's default index. If None and 
            var in self.variables, variable default index will be used.

        DESCRIPTION: A utility to allow users to express large summations 
            concisely and lazily.
        '''
        if not index:
            try:
                index = self.variables[var]['default_index']

            except KeyError:
                raise ValueError(f'Unrecognized variable name {var}')

        if not coefficients:
            return lambda: (f'{var}_{i}' for i in index())
        else:
            return lambda: (f'{coefficients[i]} {var}_{i}' for i in index())




    def write(self, output_file):
        '''
        output_file (str): path to output file
        DESCRIPTION: write model to .lp file
        '''
        
        with open(output_file, 'w') as f:
            # first write the objective function
            f.write(f'{self.objective_sense}\n')
            self.write_expr(f, self.objective_expr)

            # next write constraints
            f.write('ST\n')

            # write optional BOUNDS section

            # write optional GENERAL section

            # write optional BINARY section

            # write end
            f.write('end')

        return f'{output_file}'

    def write_expr(self, fobj, expr, appnd = None):
        '''
        fobj (file-like object): file object being written to
        expr (constraint | objective expr): either str or list of generators to 
            write
        '''
        if type(expr) == str:
            raise ValueError("usage: model.write_str_expr()")

        line = []
        line_length = 0
        for lam in expr:
            comp = lam()
            while True:
                try:
                    next_word = next(comp)
                    # check for a negative coefficient in next_word
                    if next_word[0] != '-':
                        next_word = ' + ' + next_word
                    line_length += len(next_word)
                    if line_length <= 80:
                        # with next_word, we're still beneath the line limit; 
                        #   so add next_word.
                        line.append(next_word)
                    else:
                        # with next_word, we're over the limit. FIRST write 
                        #  curernt line, THEN reset line with next_word and  
                        #   reset line_length
                        fobj.write(''.join(line + ['\n']))
                        line = [next_word]
                        line_length = len(next_word)
                except StopIteration:
                    if len(line) > 0:    
                        # make sure to write any dangling data
                        fobj.write(''.join(line + ['\n']))
                    break
        if appnd:
            # tack on the sense and rhs of a constraint
            fobj.write([w for w in appnd] + ['\n'])


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
