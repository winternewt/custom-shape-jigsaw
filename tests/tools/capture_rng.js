// Captures the JS RNG sequence from index.html's random() for deterministic-parity testing.
// Usage: node capture_rng.js <seed> <count>
const seedStart = parseInt(process.argv[2] || "0", 10);
const count = parseInt(process.argv[3] || "20", 10);
let seed = seedStart;
function random() { var x = Math.sin(seed) * 10000; seed += 1; return x - Math.floor(x); }
const out = [];
for (let i = 0; i < count; i++) out.push(random());
console.log(JSON.stringify({ seed: seedStart, count, values: out }));
