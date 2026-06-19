#!/usr/bin/env python3
"""
Comprehensive test suite for CognitiveKV Runtime v1.0
Tests all major components with proper error handling and detailed reporting.
"""

import sys
import json
import traceback
from pathlib import Path

# Try to run the smoke test from the main file
def run_comprehensive_tests():
    """Run all smoke tests and report results."""
    
    results = {
        "environment": {
            "python_version": sys.version,
            "platform": sys.platform,
        },
        "tests": {},
        "summary": {
            "passed": 0,
            "failed": 0,
            "errors": []
        }
    }
    
    # Test 1: Basic imports and initialization
    print("=" * 80)
    print("TEST 1: Basic Module Import and Initialization")
    print("=" * 80)
    
    try:
        # Import the main module
        import cognitivekv_runtime_v1_0_FIXED as ckv
        print("✓ Module imported successfully")
        
        # Test basic cache creation
        cache = ckv.CognitiveTensorCache(
            max_size_l1=10,
            max_size_l2=20,
            enable_numpy_fallback_semantics=True,
            tensor_compression=False,
            checkpoint_strategy="manual",
            paged_kv_enabled=False,  # Disable paged KV for simpler test
            radix_kv_enabled=False,
        )
        print("✓ CognitiveTensorCache created successfully")
        print(f"  - Version: {cache.VERSION}")
        print(f"  - L1 size: {cache.max_size_l1}")
        print(f"  - L2 size: {cache.max_size_l2}")
        
        results["tests"]["initialization"] = {
            "status": "PASSED",
            "version": cache.VERSION,
        }
        results["summary"]["passed"] += 1
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        results["tests"]["initialization"] = {
            "status": "FAILED",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        results["summary"]["failed"] += 1
        results["summary"]["errors"].append(f"Initialization: {str(e)}")
    
    # Test 2: Basic put/get operations
    print("\n" + "=" * 80)
    print("TEST 2: Basic Put/Get Operations")
    print("=" * 80)
    
    try:
        cache = ckv.CognitiveTensorCache(
            max_size_l1=10,
            max_size_l2=20,
            paged_kv_enabled=False,
            radix_kv_enabled=False,
        )
        
        # Test string values
        cache.put("key1", "value1")
        val = cache.get("key1")
        assert val == "value1", f"Expected 'value1', got {val}"
        print("✓ String put/get works")
        
        # Test dict values
        cache.put("key2", {"nested": "data", "number": 42})
        val = cache.get("key2")
        assert val["number"] == 42, "Dict get failed"
        print("✓ Dict put/get works")
        
        # Test list values
        cache.put("key3", [1, 2, 3, 4, 5])
        val = cache.get("key3")
        assert val == [1, 2, 3, 4, 5], "List get failed"
        print("✓ List put/get works")
        
        # Test miss
        val = cache.get("nonexistent", default="default_value")
        assert val == "default_value", "Default return failed"
        print("✓ Cache miss with default works")
        
        results["tests"]["basic_operations"] = {
            "status": "PASSED",
            "operations": ["string", "dict", "list", "miss_with_default"]
        }
        results["summary"]["passed"] += 1
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        results["tests"]["basic_operations"] = {
            "status": "FAILED",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        results["summary"]["failed"] += 1
        results["summary"]["errors"].append(f"Basic operations: {str(e)}")
    
    # Test 3: Eviction and LRU
    print("\n" + "=" * 80)
    print("TEST 3: Eviction and LRU Behavior")
    print("=" * 80)
    
    try:
        cache = ckv.CognitiveTensorCache(
            max_size_l1=3,
            max_size_l2=5,
            eviction_strategy="lru",
            paged_kv_enabled=False,
            radix_kv_enabled=False,
        )
        
        # Fill cache beyond L1 capacity
        for i in range(10):
            cache.put(f"key_{i}", f"value_{i}")
        
        print(f"✓ Added 10 items to cache with max_size_l1=3")
        print(f"  - L1 size: {len(cache.l1_cache)}")
        print(f"  - L2 size: {len(cache.l2_cache)}")
        print(f"  - Total evictions: {cache.eviction_count}")
        
        # Verify L1 not over capacity
        assert len(cache.l1_cache) <= 3, f"L1 exceeds max: {len(cache.l1_cache)}"
        print("✓ L1 capacity respected")
        
        # Verify L2 not over capacity
        assert len(cache.l2_cache) <= 5, f"L2 exceeds max: {len(cache.l2_cache)}"
        print("✓ L2 capacity respected")
        
        results["tests"]["eviction"] = {
            "status": "PASSED",
            "l1_size": len(cache.l1_cache),
            "l2_size": len(cache.l2_cache),
            "evictions": cache.eviction_count
        }
        results["summary"]["passed"] += 1
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        results["tests"]["eviction"] = {
            "status": "FAILED",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        results["summary"]["failed"] += 1
        results["summary"]["errors"].append(f"Eviction: {str(e)}")
    
    # Test 4: NumPy tensor handling
    print("\n" + "=" * 80)
    print("TEST 4: NumPy Tensor Handling")
    print("=" * 80)
    
    try:
        import numpy as np
        
        cache = ckv.CognitiveTensorCache(
            max_size_l1=10,
            max_size_l2=20,
            tensor_compression=True,
            paged_kv_enabled=False,
            radix_kv_enabled=False,
        )
        
        # Create tensors
        tensor1 = np.random.randn(10, 10).astype(np.float32)
        tensor2 = np.random.randn(5, 5, 5).astype(np.float32)
        
        # Store tensors
        cache.put_tensor("tensor1", tensor1, importance=0.8)
        cache.put_tensor("tensor2", tensor2, importance=0.9)
        print("✓ Tensors stored successfully")
        
        # Retrieve tensors
        retrieved1 = cache.get_tensor("tensor1")
        retrieved2 = cache.get_tensor("tensor2")
        
        assert retrieved1 is not None, "Tensor1 retrieval failed"
        assert retrieved2 is not None, "Tensor2 retrieval failed"
        assert np.allclose(retrieved1, tensor1), "Tensor1 values don't match"
        assert np.allclose(retrieved2, tensor2), "Tensor2 values don't match"
        print("✓ Tensor values match after retrieval")
        
        # Check tensor metadata
        tensor_list = cache.list_tensors()
        assert len(tensor_list) >= 2, "Not all tensors listed"
        print(f"✓ Found {len(tensor_list)} tensors in cache")
        
        results["tests"]["numpy_tensors"] = {
            "status": "PASSED",
            "tensors_stored": 2,
            "tensors_retrieved": 2,
            "metadata_count": len(tensor_list)
        }
        results["summary"]["passed"] += 1
        
    except ImportError:
        print("⊘ NumPy not available, skipping test")
        results["tests"]["numpy_tensors"] = {
            "status": "SKIPPED",
            "reason": "NumPy not installed"
        }
    except Exception as e:
        print(f"✗ FAILED: {e}")
        results["tests"]["numpy_tensors"] = {
            "status": "FAILED",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        results["summary"]["failed"] += 1
        results["summary"]["errors"].append(f"NumPy tensors: {str(e)}")
    
    # Test 5: Statistics and monitoring
    print("\n" + "=" * 80)
    print("TEST 5: Statistics and Monitoring")
    print("=" * 80)
    
    try:
        cache = ckv.CognitiveTensorCache(
            max_size_l1=10,
            max_size_l2=20,
            enable_monitoring=True,
            paged_kv_enabled=False,
            radix_kv_enabled=False,
        )
        
        # Generate some activity
        for i in range(20):
            cache.put(f"key_{i}", f"value_{i}")
            if i % 2 == 0:
                cache.get(f"key_{i}")
        
        stats = cache.get_stats()
        print("✓ Statistics retrieved successfully")
        print(f"  - Hit rate: {stats['hit_rate']}")
        print(f"  - L1 utilization: {stats['l1_utilization']}")
        print(f"  - L2 utilization: {stats['l2_utilization']}")
        print(f"  - Evictions: {stats['eviction_count']}")
        
        assert "hit_count" in stats, "Missing hit_count"
        assert "miss_count" in stats, "Missing miss_count"
        assert "eviction_count" in stats, "Missing eviction_count"
        
        results["tests"]["statistics"] = {
            "status": "PASSED",
            "hit_rate": stats['hit_rate'],
            "l1_utilization": stats['l1_utilization'],
            "l2_utilization": stats['l2_utilization'],
        }
        results["summary"]["passed"] += 1
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        results["tests"]["statistics"] = {
            "status": "FAILED",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        results["summary"]["failed"] += 1
        results["summary"]["errors"].append(f"Statistics: {str(e)}")
    
    # Test 6: Batch operations
    print("\n" + "=" * 80)
    print("TEST 6: Batch Operations")
    print("=" * 80)
    
    try:
        cache = ckv.CognitiveTensorCache(
            max_size_l1=10,
            max_size_l2=20,
            paged_kv_enabled=False,
            radix_kv_enabled=False,
        )
        
        # Batch put
        batch_data = {f"batch_key_{i}": f"batch_value_{i}" for i in range(5)}
        cache.batch_put(batch_data)
        print("✓ Batch put successful")
        
        # Batch get
        keys = list(batch_data.keys())
        retrieved = cache.batch_get(keys)
        print(f"✓ Batch get successful, retrieved {len(retrieved)} items")
        
        assert len(retrieved) == 5, "Batch get returned wrong number of items"
        
        # Batch delete
        cache.batch_delete(keys[:3])
        print("✓ Batch delete successful")
        
        remaining = cache.batch_get(keys)
        non_deleted = sum(1 for v in remaining.values() if v is not None)
        assert non_deleted == 2, f"Expected 2 remaining, got {non_deleted}"
        print(f"✓ Verified {non_deleted} items remain after batch delete")
        
        results["tests"]["batch_operations"] = {
            "status": "PASSED",
            "batch_put": 5,
            "batch_get": 5,
            "batch_delete": 3,
            "remaining": 2
        }
        results["summary"]["passed"] += 1
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        results["tests"]["batch_operations"] = {
            "status": "FAILED",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        results["summary"]["failed"] += 1
        results["summary"]["errors"].append(f"Batch operations: {str(e)}")
    
    # Test 7: Tags and invalidation
    print("\n" + "=" * 80)
    print("TEST 7: Tags and Invalidation")
    print("=" * 80)
    
    try:
        cache = ckv.CognitiveTensorCache(
            max_size_l1=10,
            max_size_l2=20,
            paged_kv_enabled=False,
            radix_kv_enabled=False,
        )
        
        # Put items with tags
        cache.put("user_1_data", {"id": 1}, tags={"user_1", "data"})
        cache.put("user_1_cache", {"cached": True}, tags={"user_1", "cache"})
        cache.put("user_2_data", {"id": 2}, tags={"user_2", "data"})
        print("✓ Items stored with tags")
        
        # Invalidate by tag
        invalidated = cache.invalidate_by_tag("user_1")
        print(f"✓ Invalidated {invalidated} items with tag 'user_1'")
        
        assert invalidated == 2, f"Expected to invalidate 2 items, got {invalidated}"
        
        # Verify user_1 items are gone
        assert cache.get("user_1_data") is None, "user_1_data should be deleted"
        assert cache.get("user_1_cache") is None, "user_1_cache should be deleted"
        
        # Verify user_2 item remains
        assert cache.get("user_2_data") is not None, "user_2_data should remain"
        print("✓ Verified tag-based invalidation worked correctly")
        
        results["tests"]["tags_invalidation"] = {
            "status": "PASSED",
            "items_tagged": 3,
            "items_invalidated": 2,
            "items_remaining": 1
        }
        results["summary"]["passed"] += 1
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        results["tests"]["tags_invalidation"] = {
            "status": "FAILED",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        results["summary"]["failed"] += 1
        results["summary"]["errors"].append(f"Tags/invalidation: {str(e)}")
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"✓ PASSED: {results['summary']['passed']}")
    print(f"✗ FAILED: {results['summary']['failed']}")
    
    if results['summary']['errors']:
        print("\nErrors encountered:")
        for error in results['summary']['errors']:
            print(f"  - {error}")
    
    print("\n" + "=" * 80)
    print("Full Results (JSON):")
    print("=" * 80)
    print(json.dumps(results, indent=2, default=str))
    
    return results

if __name__ == "__main__":
    run_comprehensive_tests()
