def foo(a, b=10):
    m = a + b
    n = m * b
    return n

def main():
    e = foo(8)
    c = foo(4, 5)
    d = foo(6, b=3)
    n = c + d + e
    print(n)
    return n

main()