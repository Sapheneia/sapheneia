#!/bin/bash

echo "Fetching Prediction Data..."

# Accept input from stdin
json_input=$(cat)

# Extract and format using jq
# Supports both old format (.prediction) and new format (.forecast + .quantiles array)
echo "$json_input" | jq -r '
  "Step\tBEARISH(10%)\tMEDIAN(50%)\tBULLISH(90%)",
  "----\t------------\t-----------\t------------",
  (
    if .forecast then
      # New API format
      [
        (.quantiles | map(select(.quantile == 0.1)) | .[0].values),
        .forecast.values,
        (.quantiles | map(select(.quantile == 0.9)) | .[0].values)
      ]
    else
      # Old format
      [
        .prediction.quantiles["10"],
        .prediction.median,
        .prediction.quantiles["90"]
      ]
    end
    | transpose
    | to_entries
    | .[]
    | "\(.key + 1)\t\(.value[0] | floor)\t\t\(.value[1] | floor)\t\t\(.value[2] | floor)"
  )
' | column -t -s $'\t'