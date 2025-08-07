#!/bin/bash

# Simple curl-based recovery test script
# Tests the force recovery endpoint on the corrupted dream

DREAM_ID="c18af0e9-cd54-4e61-8106-74487472b90e"
API_BASE="http://localhost:8000"

echo "=============================================================="
echo "🔧 TRANSCRIPTION RECOVERY TEST"
echo "=============================================================="
echo "Target Dream ID: $DREAM_ID"
echo "API Base URL: $API_BASE"
echo "Test Time: $(date)"
echo ""

# Check if server is running
echo "📡 Testing server connectivity..."
if curl -s -f "$API_BASE/" > /dev/null 2>&1 || curl -s "$API_BASE/" 2>&1 | grep -q "404\|422\|200"; then
    echo "✅ Server is responding"
else
    echo "❌ Server is not responding - make sure backend is running on localhost:8000"
    exit 1
fi

# Get JWT token
echo ""
echo "🔐 Authentication Setup"
if [ -n "$JWT_TOKEN" ]; then
    echo "✅ Using JWT token from environment variable"
    AUTH_HEADER="Authorization: Bearer $JWT_TOKEN"
elif [ -n "$1" ]; then
    echo "✅ Using JWT token from command line argument"
    AUTH_HEADER="Authorization: Bearer $1"
else
    echo "❌ No JWT token provided"
    echo "   Usage: $0 <jwt_token>"
    echo "   Or set JWT_TOKEN environment variable"
    echo "   Example: JWT_TOKEN=your_token_here $0"
    exit 1
fi

echo ""
echo "=============================================================="
echo "📊 PRE-RECOVERY STATUS CHECK"
echo "=============================================================="

# Check dream status before recovery
echo "🔍 Checking dream segments status..."
SEGMENTS_RESPONSE=$(curl -s -H "$AUTH_HEADER" "$API_BASE/dreams/$DREAM_ID/segments/status")
SEGMENTS_STATUS=$?

if [ $SEGMENTS_STATUS -eq 0 ]; then
    echo "✅ Segments status retrieved"
    
    # Parse the response to count failed segments (basic JSON parsing)
    FAILED_COUNT=$(echo "$SEGMENTS_RESPONSE" | grep -o '"transcription_status":"failed"' | wc -l | tr -d ' ')
    COMPLETED_COUNT=$(echo "$SEGMENTS_RESPONSE" | grep -o '"transcription_status":"completed"' | wc -l | tr -d ' ')
    TOTAL_SEGMENTS=$(echo "$SEGMENTS_RESPONSE" | grep -o '"transcription_status":' | wc -l | tr -d ' ')
    
    echo "   📊 Total segments: $TOTAL_SEGMENTS"
    echo "   ❌ Failed segments: $FAILED_COUNT" 
    echo "   ✅ Completed segments: $COMPLETED_COUNT"
    
    if [ "$FAILED_COUNT" = "0" ]; then
        echo "✅ No failed segments found - dream may already be recovered!"
        exit 0
    fi
else
    echo "❌ Failed to get segments status"
    exit 1
fi

echo ""
echo "=============================================================="
echo "🚀 FORCE RECOVERY EXECUTION"
echo "=============================================================="

echo "🔧 Triggering force recovery..."

# Execute force recovery
RECOVERY_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -H "$AUTH_HEADER" -X POST "$API_BASE/dreams/$DREAM_ID/force-recovery")
RECOVERY_STATUS=$(echo "$RECOVERY_RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
RECOVERY_BODY=$(echo "$RECOVERY_RESPONSE" | sed '/HTTP_STATUS:/d')

echo "📡 Recovery request completed (HTTP $RECOVERY_STATUS)"

if [ "$RECOVERY_STATUS" = "200" ]; then
    echo "✅ Recovery endpoint executed successfully"
    echo ""
    echo "📋 Recovery Response:"
    echo "$RECOVERY_BODY" | python3 -m json.tool 2>/dev/null || echo "$RECOVERY_BODY"
    
    # Check if recovery was successful
    if echo "$RECOVERY_BODY" | grep -q '"success":true'; then
        echo ""
        echo "🎉 Recovery reported SUCCESS!"
        
        # Check if transcript was generated
        if echo "$RECOVERY_BODY" | grep -q '"has_transcript":true'; then
            echo "✅ Dream now has transcript!"
        else
            echo "⚠️  Recovery succeeded but no transcript reported"
        fi
    else
        echo ""
        echo "❌ Recovery reported FAILURE"
        ERROR_MSG=$(echo "$RECOVERY_BODY" | grep -o '"error":"[^"]*"' | cut -d'"' -f4)
        if [ -n "$ERROR_MSG" ]; then
            echo "   Error: $ERROR_MSG"
        fi
    fi
    
elif [ "$RECOVERY_STATUS" = "401" ]; then
    echo "❌ Authentication failed - invalid JWT token"
    exit 1
elif [ "$RECOVERY_STATUS" = "404" ]; then
    echo "❌ Dream not found"
    exit 1
elif [ "$RECOVERY_STATUS" = "500" ]; then
    echo "❌ Server error during recovery:"
    echo "$RECOVERY_BODY"
    exit 1
else
    echo "❌ Recovery failed with HTTP $RECOVERY_STATUS"
    echo "Response: $RECOVERY_BODY"
    exit 1
fi

echo ""
echo "=============================================================="
echo "📊 POST-RECOVERY STATUS CHECK"  
echo "=============================================================="

# Brief pause to let server update
sleep 2

echo "🔍 Checking post-recovery segments status..."
POST_SEGMENTS_RESPONSE=$(curl -s -H "$AUTH_HEADER" "$API_BASE/dreams/$DREAM_ID/segments/status")
POST_SEGMENTS_STATUS=$?

if [ $POST_SEGMENTS_STATUS -eq 0 ]; then
    echo "✅ Post-recovery status retrieved"
    
    # Parse the response to count failed segments
    POST_FAILED_COUNT=$(echo "$POST_SEGMENTS_RESPONSE" | grep -o '"transcription_status":"failed"' | wc -l | tr -d ' ')
    POST_COMPLETED_COUNT=$(echo "$POST_SEGMENTS_RESPONSE" | grep -o '"transcription_status":"completed"' | wc -l | tr -d ' ')
    POST_PENDING_COUNT=$(echo "$POST_SEGMENTS_RESPONSE" | grep -o '"transcription_status":"pending"' | wc -l | tr -d ' ')
    
    echo "   📊 Total segments: $TOTAL_SEGMENTS" 
    echo "   ❌ Failed segments: $POST_FAILED_COUNT"
    echo "   ✅ Completed segments: $POST_COMPLETED_COUNT"
    echo "   ⏳ Pending segments: $POST_PENDING_COUNT"
    
    # Determine success level
    if [ "$POST_FAILED_COUNT" = "0" ] && [ "$POST_COMPLETED_COUNT" -gt "0" ]; then
        echo ""
        echo "🎉 COMPLETE SUCCESS - All segments recovered!"
        SUCCESS_LEVEL="COMPLETE"
    elif [ "$POST_FAILED_COUNT" = "0" ] && [ "$POST_PENDING_COUNT" -gt "0" ]; then
        echo ""
        echo "🔄 PARTIAL SUCCESS - Segments now pending (will be processed)"
        SUCCESS_LEVEL="PARTIAL"
    elif [ "$POST_FAILED_COUNT" -lt "$FAILED_COUNT" ]; then
        echo ""
        echo "📈 PARTIAL SUCCESS - Some segments recovered"
        SUCCESS_LEVEL="PARTIAL"
    else
        echo ""
        echo "❌ NO PROGRESS - All segments still failed"
        SUCCESS_LEVEL="FAILED"
    fi
else
    echo "❌ Failed to get post-recovery status"
    SUCCESS_LEVEL="UNKNOWN"
fi

echo ""
echo "=============================================================="
echo "📋 TEST SUMMARY"
echo "=============================================================="
echo "✅ Test completed at $(date)"
echo "🎯 Result: $SUCCESS_LEVEL SUCCESS"
echo ""
echo "📋 Next Steps:"
echo "   1. Check backend logs for detailed recovery process information"
echo "   2. Try viewing the dream in the app to see if errors are resolved"
echo "   3. Verify that analysis/summary generation now works"
echo ""
echo "🔧 Backend logs should show:"
echo "   - 'Generating presigned URL for S3 key: ...' (debug)"
echo "   - 'Generated presigned URL for segment ...' (debug)"
echo "   - 'Successfully recovered segment ...' (info)"
echo ""

if [ "$SUCCESS_LEVEL" = "COMPLETE" ] || [ "$SUCCESS_LEVEL" = "PARTIAL" ]; then
    echo "🎉 The transcription recovery fix appears to be working!"
    exit 0
else
    echo "❌ Recovery may need additional investigation"
    exit 1
fi