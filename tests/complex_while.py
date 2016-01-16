def foo():
    a = 1
    b = 8
    c = 8
    d = 10
    while b > 3:
        a +=1
        b -= 1
        while c > 4:
            b -= 2
            c -= 1
            while d > 4:
                b -= 1
                d -= 1

    print(a, b, c, d)

foo()