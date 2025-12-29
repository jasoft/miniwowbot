
class MyDict(dict):
    def __bool__(self):
        return False

d = MyDict({"a": 1})
print(f"Bool value: {bool(d)}")
print(f"Content: {d}")
