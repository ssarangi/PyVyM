class Point:
    def __init__(self, x, y):
        self.x = x * 8
        self.y = y * 5

    def print(self):
        return str(self.x) + str(self.y)

def ChangePoint():
    obj1 = Point(1, 2)
    obj2 = Point(3, 4)

    obj1.a = 5
    obj1.b = 10

    obj2.b = 5
    obj2.a = 10

    if obj1.a > 5:
        obj2.b = 1
    else:
        obj2.a = 2

    return obj1.a * obj1.b + obj2.a * obj2.b


ChangePoint()