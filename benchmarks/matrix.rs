use std::env;

fn main() {
    let n: usize = env::args().nth(1).and_then(|s| s.parse().ok()).unwrap_or(200);
    let size = n * n;

    let mut a = vec![0i64; size];
    let mut b = vec![0i64; size];
    let mut c = vec![0i64; size];

    for i in 0..size {
        a[i] = (i % 10) as i64;
        b[i] = ((i * 2) % 10) as i64;
    }

    for i in 0..n {
        for j in 0..n {
            let mut s: i64 = 0;
            for k in 0..n {
                s += a[i * n + k] * b[k * n + j];
            }
            c[i * n + j] = s;
        }
    }

    let total: i64 = c.iter().sum();
    println!("{}", total);
}