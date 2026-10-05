import time

def somar(a, b): return a + b
def dividir(a, b): return 0 if b == 0 else a // b

def test_somar_1(): assert somar(2, 2) == 4
def test_somar_2(): assert somar(10, 50) == 60
def test_dividir_1(): assert dividir(10, 2) == 5
def test_dividir_2(): assert dividir(10, 0) == 0
def test_loop_pesado():
    x = 0
    for i in range(1000000): x += i
    assert x == 499999500000

if __name__ == "__main__":
    start = time.time()
    
    test_somar_1()
    test_somar_2()
    test_dividir_1()
    test_dividir_2()
    test_loop_pesado()
    
    end = time.time()
    print(f"Python Runtime: {end - start:.6f} segundos")
