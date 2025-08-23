"""
Optimized BitVMX Script Generator with caching and parallel processing
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import hashlib
import json

# Create a simplified cache key from setup properties
def create_cache_key(max_steps, search_iterations, input_words):
    """Create cache key for script generation"""
    key = f"{max_steps}_{search_iterations}_{input_words}"
    return hashlib.md5(key.encode()).hexdigest()

class OptimizedScriptGenerator:
    """Optimized script generator with caching and parallel processing"""
    
    def __init__(self):
        self.cache = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    @lru_cache(maxsize=128)
    def generate_hash_script(self, step_index, max_steps):
        """Generate hash script with caching"""
        # Simulate script generation (in reality, this would be actual script)
        time.sleep(0.001)  # Simulate work
        return f"hash_script_{step_index}"
    
    @lru_cache(maxsize=128)
    def generate_choice_script(self, step_index, max_steps):
        """Generate choice script with caching"""
        time.sleep(0.001)  # Simulate work
        return f"choice_script_{step_index}"
    
    def generate_scripts_parallel(self, max_steps, search_iterations):
        """Generate scripts in parallel"""
        hash_scripts = []
        choice_scripts = []
        
        # Generate scripts in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit hash script generation tasks
            hash_futures = {
                executor.submit(self.generate_hash_script, i, max_steps): i 
                for i in range(search_iterations)
            }
            
            # Submit choice script generation tasks
            choice_futures = {
                executor.submit(self.generate_choice_script, i, max_steps): i 
                for i in range(search_iterations)
            }
            
            # Collect hash scripts
            for future in as_completed(hash_futures):
                idx = hash_futures[future]
                script = future.result()
                hash_scripts.append((idx, script))
            
            # Collect choice scripts
            for future in as_completed(choice_futures):
                idx = choice_futures[future]
                script = future.result()
                choice_scripts.append((idx, script))
        
        # Sort by index to maintain order
        hash_scripts.sort(key=lambda x: x[0])
        choice_scripts.sort(key=lambda x: x[0])
        
        return [s[1] for s in hash_scripts], [s[1] for s in choice_scripts]
    
    def generate_optimized(self, max_steps, search_iterations, input_words):
        """Main optimized generation method"""
        start_time = time.time()
        
        # Check cache
        cache_key = create_cache_key(max_steps, search_iterations, input_words)
        if cache_key in self.cache:
            print(f"[CACHE HIT] Returning cached scripts for key {cache_key}")
            return self.cache[cache_key]
        
        print(f"[OPTIMIZED] Generating scripts for {search_iterations} iterations...")
        
        # Generate in parallel
        hash_scripts, choice_scripts = self.generate_scripts_parallel(
            max_steps, search_iterations
        )
        
        result = {
            "hash_scripts": hash_scripts,
            "choice_scripts": choice_scripts,
            "generation_time": time.time() - start_time
        }
        
        # Cache result
        self.cache[cache_key] = result
        
        print(f"[OPTIMIZED] Generated {len(hash_scripts)} scripts in {result['generation_time']:.2f}s")
        
        return result

def test_optimization():
    """Test the optimization"""
    generator = OptimizedScriptGenerator()
    
    # Test parameters
    test_cases = [
        (100, 3, 20),   # Small
        (1000, 5, 20),  # Medium
        (10000, 3, 20), # Large (current)
    ]
    
    for max_steps, search_iter, input_words in test_cases:
        print(f"\nTest: max_steps={max_steps}, iterations={search_iter}")
        
        # First run (no cache)
        result1 = generator.generate_optimized(max_steps, search_iter, input_words)
        print(f"  First run: {result1['generation_time']:.3f}s")
        
        # Second run (cached)
        result2 = generator.generate_optimized(max_steps, search_iter, input_words)
        print(f"  Cached run: {result2['generation_time']:.3f}s")

if __name__ == "__main__":
    test_optimization()