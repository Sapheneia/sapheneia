#!/bin/bash

echo "Fetching Prediction Data..."

# Accept input from stdin
json_input=$(cat)

# Extract and format using jq
echo "$json_input" | jq -r '
  "Step\tBEARISH(10%)\tMEDIAN(50%)\tBULLISH(90%)",
  "----\t------------\t-----------\t------------",
  (
    [
      .prediction.quantiles["10"],
      .prediction.median,
      .prediction.quantiles["90"]
    ]
    | transpose
    | to_entries
    | .[]
    | "\(.key + 1)\t\(.value[0] | floor)\t\t\(.value[1] | floor)\t\t\(.value[2] | floor)"
  )
' | column -t -s $'\t'