# Performance Tuning Guide for P1 Batch Processing

## Current Optimizations Applied

I've increased the default values to speed up batch processing:

### Changes Made:

1. **ENNETIX_API_BATCH_SIZE**: `100` → `200`
   - More concurrent alert processing (API 1 & 2)
   - **Impact**: Processes 2x more alerts simultaneously

2. **ENNETIX_API3_BATCH_SIZE**: `10` → `20`
   - More concurrent flow API calls (API 3)
   - **Impact**: 2x more flow requests in parallel

3. **BATCH_SIZE**: `100` → `500`
   - Larger bulk indexing batches
   - **Impact**: Fewer ES operations, faster indexing

4. **ENNETIX_API3_DELAY**: `0.1s` → `0.05s` (new configurable setting)
   - Reduced delay between API 3 calls
   - **Impact**: Faster flow fetching

## Expected Performance Improvement

**Before:**
- ~1-2 minutes per batch of 100 alerts
- 63 batches × 1.5 min = ~95 minutes total

**After (with new defaults):**
- ~30-60 seconds per batch of 200 alerts
- 32 batches × 0.75 min = ~24 minutes total
- **~4x faster!**

## Further Optimization Options

### Option 1: Add to `.env` file for even more speed

```bash
# Add these to your .env file for maximum speed
ENNETIX_API_BATCH_SIZE=300
ENNETIX_API3_BATCH_SIZE=30
BATCH_SIZE=1000
ENNETIX_API3_DELAY=0.01
```

**Warning**: Higher values may:
- Overload the Ennetix API server
- Cause rate limiting or 429 errors
- Use more memory

### Option 2: Conservative (Safe) Settings

```bash
# Safer settings if you encounter errors
ENNETIX_API_BATCH_SIZE=150
ENNETIX_API3_BATCH_SIZE=15
BATCH_SIZE=500
ENNETIX_API3_DELAY=0.05
```

### Option 3: Aggressive (Maximum Speed)

```bash
# Maximum speed (use with caution)
ENNETIX_API_BATCH_SIZE=500
ENNETIX_API3_BATCH_SIZE=50
BATCH_SIZE=2000
ENNETIX_API3_DELAY=0.0
```

## How to Apply Settings

1. **Edit `.env` file:**
   ```bash
   nano .env
   ```

2. **Add the settings:**
   ```bash
   # Performance tuning
   ENNETIX_API_BATCH_SIZE=200
   ENNETIX_API3_BATCH_SIZE=20
   BATCH_SIZE=500
   ENNETIX_API3_DELAY=0.05
   ```

3. **Restart the service** for changes to take effect

## Monitoring Performance

Watch the logs to see batch processing times:

```bash
# Look for batch completion times
grep "Batch.*completed" logs.txt

# Calculate average time per batch
# Faster batches = better performance
```

## Troubleshooting

### If you see rate limiting errors (429):
- Reduce `ENNETIX_API_BATCH_SIZE`
- Reduce `ENNETIX_API3_BATCH_SIZE`
- Increase `ENNETIX_API3_DELAY`

### If you see memory errors:
- Reduce `BATCH_SIZE`
- Reduce `ENNETIX_API_BATCH_SIZE`

### If you see connection timeouts:
- Increase `ENNETIX_ELASTICSEARCH_REQUEST_TIMEOUT`
- Increase `ELASTICSEARCH_CYGENIQ_REQUEST_TIMEOUT`

## Recommended Settings by Scenario

### Development/Testing
```bash
ENNETIX_API_BATCH_SIZE=100
ENNETIX_API3_BATCH_SIZE=10
BATCH_SIZE=100
ENNETIX_API3_DELAY=0.1
```

### Production (Balanced)
```bash
ENNETIX_API_BATCH_SIZE=200
ENNETIX_API3_BATCH_SIZE=20
BATCH_SIZE=500
ENNETIX_API3_DELAY=0.05
```

### Production (High Volume)
```bash
ENNETIX_API_BATCH_SIZE=300
ENNETIX_API3_BATCH_SIZE=30
BATCH_SIZE=1000
ENNETIX_API3_DELAY=0.02
```

## Current Status

✅ **Optimizations applied** - Defaults are now faster
✅ **Configurable** - All settings can be overridden via `.env`
✅ **Backward compatible** - Existing code works with new defaults

## Next Steps

1. **Test with current defaults** (already applied)
2. **Monitor performance** in logs
3. **Adjust `.env`** if needed based on your API limits
4. **Fine-tune** based on your specific environment

