def foo(a):
    b = a * 5
    print("Value of b: %s" % b)
    return b

def main():
    d = 5
    e = 6
    m = d + e
    return foo(m)

main()