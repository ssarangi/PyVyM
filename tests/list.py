def mylist():
    thislist = []
    thislist.append(1)
    thislist.append(2)
    thislist.append(3)
    n = thislist.pop()
    print(n)
    return n

def main():
    mylist()

main()