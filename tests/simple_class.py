class Foo:
    def __init__(self):
        self.member1 = 1

    def print(self):
        self.member1 += 5
        print("Member1: %s" % self.member1)

def main():
    foo = Foo()
    foo.print()

main()