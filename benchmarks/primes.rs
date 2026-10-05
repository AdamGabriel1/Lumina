use std::env;

fn main() {
    let limit: usize = env::args().nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(10_000_000);

    let mut primes = vec![1u8; limit];
    if limit > 0 { primes[0] = 0; }
    if limit > 1 { primes[1] = 0; }

    let mut p = 2usize;
    while p * p < limit {
        if primes[p] == 1 {
            let mut i = p * p;
            while i < limit {
                primes[i] = 0;
                i += p;
            }
        }
        p += 1;
    }

    let count = primes.iter().filter(|&&x| x == 1).count();
    println!("{}", count);
}