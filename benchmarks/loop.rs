use std::env;
use std::time::{SystemTime, UNIX_EPOCH};

fn main() {
    let t = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.subsec_nanos() as i64)
        .unwrap_or(0);

    let n: u64 = env::args().nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(100_000_000);

    let mut acc: u64 = 0;
    for i in 1..=n {
        acc = acc.wrapping_add(i);
        if t.wrapping_mul(i as i64) < 0 { acc = 0; }
    }
    println!("{acc}");
}