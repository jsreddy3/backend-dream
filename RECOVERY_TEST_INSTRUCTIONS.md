# Recovery Test Instructions

## Current Status ✅
- **Backend server**: Running and accessible on localhost:8000
- **Code fixes**: Implemented and ready for testing
- **Test scripts**: Created and ready to use

## Quick Test Command

To test the recovery fix on the corrupted dream, run:

```bash
cd /Users/shanreddy/Documents/Development/Dream/backend-dream

# Option 1: Use environment variable
JWT_TOKEN="your_jwt_token_here" ./test_recovery_simple.sh

# Option 2: Pass token as argument  
./test_recovery_simple.sh "your_jwt_token_here"
```

## How to Get a JWT Token

You'll need a valid JWT token for authentication. You can get one by:

1. **From the iOS app**: Check the auth store or logs for the current JWT token
2. **From existing test files**: Look for tokens in test scripts like `test_token.txt`
3. **Generate new one**: Use your existing auth flow to create a fresh token

## Expected Results

### If the fix works correctly:
```
🎉 COMPLETE SUCCESS - All segments recovered!
```

The script should show:
- Failed segments changing from 2 to 0
- Completed segments increasing
- Dream now has transcript
- Backend logs showing presigned URL generation

### Backend logs should contain:
```
DEBUG: Generating presigned URL for S3 key: dreams/c18af0e9-cd54-4e61-8106-74487472b90e/...
DEBUG: Generated presigned URL for segment 802e8f59-2379-4de0-bd0f-650522727d02
Successfully recovered segment 802e8f59-2379-4de0-bd0f-650522727d02: 1234 chars
```

### If something goes wrong:
The script will show detailed error information to help debug the issue.

## Manual Testing Alternative

If you prefer to test manually:

```bash
# Check dream status
curl -H "Authorization: Bearer YOUR_TOKEN" \
     "http://localhost:8000/dreams/c18af0e9-cd54-4e61-8106-74487472b90e/segments/status"

# Trigger recovery
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
     "http://localhost:8000/dreams/c18af0e9-cd54-4e61-8106-74487472b90e/force-recovery"

# Check status again
curl -H "Authorization: Bearer YOUR_TOKEN" \
     "http://localhost:8000/dreams/c18af0e9-cd54-4e61-8106-74487472b90e/segments/status"
```

## After Recovery Testing

Once the recovery works:

1. **Test the frontend**: Try viewing the dream in the iOS app - it should no longer show error messages
2. **Verify analysis**: The dream should now be able to generate summaries and analysis
3. **Check for new errors**: Monitor logs to ensure no new AttributeError exceptions occur

## Files Created for Testing

- `test_recovery_simple.sh` - Main test script (bash/curl based)
- `test_force_recovery.py` - Advanced test script (Python/httpx based) 
- `TRANSCRIPTION_FIX_SUMMARY.md` - Complete documentation of all changes made

The fix is ready - we just need to execute the recovery test with proper authentication!