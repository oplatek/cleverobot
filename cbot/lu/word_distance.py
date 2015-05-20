class WordDistance:
    '''Computes the min edit operations from target to source.'''

    def __init__(self, source, target, penalties=None):
        '''Init the object for computing distance shortest common path etc..

        :param target: a target sequence
        :param source: a source sequence
        :param cost: an expression for computing cost of the edit operations
        '''
        self.s = source
        self.t = target
        self.a = None
        if penalties is None:
            penalties = (1, 2, 1)
        self.pi, self.ps, self.pd = penalties

    def compute_table(self):
        '''Compute table by dynamic programming
        representing distance between 
        source(rows) and target(columns)

        :return table = list of lists [len(source)] x [len(target)]
        '''
        n = len(self.s)
        m = len(self.t)
        a = [[0.0 for i in range(m+1)] for j in range(n+1)]
        self.a = a
        for i in range(1, n + 1):
            a[i][0] = a[i-1][0] + self.pi 
        for j in range(1, m + 1):
            a[0][j] = a[0][j-1] + self.pd
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                insertion = a[i - 1][j] + self.pi 
                deletion = a[i][j-1] + self.pd 
                if self.s[i - 1] == self.t[j - 1]:
                    substitution = a[i - 1][j - 1]
                else:
                    substitution = a[i-1][j-1] + self.ps 
                self.a[i][j] = min(insertion, deletion, substitution)
        return self

    def compute_dist(self):
        '''Given compute_table returns the distance between source and target'''
        if self.a is None:
            self.compute_table()
        return self.a[len(self.s)][len(self.t)]

    def best_path(self):
        '''Return list of pairs representing operations used for transforming
        source to target.
        (None,None) - correct
        (X, Y) - substitutions X to Y
        (None, X) - insertion X
        (X, None) - delettion X

        Complexity O(m+n) given compute_table

        :return a list of operations
        '''
        if self.a is None:
            self.compute_table()
        i, j = len(self.s), len(self.t)
        d = max(i, j)
        p = []
        rsource, rtarget = list(self.s), list(self.t)
        rsource.reverse()
        rtarget.reverse()
        for l in xrange(d):
            if i == 0:
                p.append((None, rtarget[j-1]))
                j -= 1
            elif j == 0:
                p.append((rsource[i-1],None))
                i -= 1
            else:
                diag = self.a[i-1][j-1]
                ins = self.a[i][j-1]
                dele = self.a[i-1][j]
                # first try substitution
                if diag <= dele and diag <= ins:
                    if rsource[i-1] == rtarget[j-1]:
                        p.append((None, None))
                    else:
                        p.append((rsource[i-1], rtarget[j-1]))
                elif ins <= diag and ins <= dele:
                    p.append((None, rtarget[j-1]))
                elif dele <= diag and dele <= ins:
                    p.append((rsource[i-1], None))
        return p
                

    def ops_used(self): 
        '''
        Return number of insertions, deleteions, substitutions used
        in best path.
        Comlexity: O(m+n): given compute_table
        :return: a tuple of (insertions, deletions, substitutions)
        '''
        if self.a is None:
            self.compute_table()
        i, d, s = 0, 0 , 0
        for op in self.best_path():
            x, y = op
            if x is None:
                i += 1
            if y is None:
                d += 1
            if x is not None and y is not None:
                s += 1
        return (i, d, s)
