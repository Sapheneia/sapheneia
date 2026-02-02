#!/bin/bash

# Read input from stdin (pipe)
input=$(cat)

# Use jq to structure the data for awk
# Format: Step | p10 | Median | p90
# Supports both old format (.prediction) and new format (.forecast + .quantiles array)
data=$(echo "$input" | jq -r '
  if .forecast then
    # New API format: .forecast.values for median, .quantiles array for percentiles
    [
      (.quantiles | map(select(.quantile == 0.1)) | .[0].values),
      .forecast.values,
      (.quantiles | map(select(.quantile == 0.9)) | .[0].values)
    ]
    | transpose[]
    | @tsv
  else
    # Old format
    [
      .prediction.quantiles["10"],
      .prediction.median,
      .prediction.quantiles["90"]
    ]
    | transpose[]
    | @tsv
  end
')

echo "=== Aleutian/Sapheneia Forecast (Chronos-T5) ==="
echo "Range: 10th-90th Percentile | Marker: Median"
echo ""

# Process with awk to draw the chart
echo "$data" | awk '
BEGIN {
    min_val = 100000;
    max_val = -100000;
    width = 50;
}
{
    # Store data
    p10[NR] = $1;
    med[NR] = $2;
    p90[NR] = $3;

    # Find global min/max for scaling
    if ($1 < min_val) min_val = $1;
    if ($3 > max_val) max_val = $3;
}
END {
    # Add a little buffer to the scale
    range = max_val - min_val;
    if (range == 0) range = 1; # Avoid divide by zero

    for (i=1; i<=NR; i++) {
        # Calculate positions
        start_pos = int((p10[i] - min_val) / range * width);
        end_pos   = int((p90[i] - min_val) / range * width);
        med_pos   = int((med[i] - min_val) / range * width);

        # Draw the line
        printf "T+%d %6.2f |", i, med[i];

        for (j=0; j<=width; j++) {
            if (j == med_pos) {
                printf "O"; # The Median
            } else if (j >= start_pos && j <= end_pos) {
                printf "-"; # The Confidence Range
            } else {
                printf " ";
            }
        }
        printf "| (Range: %.2f - %.2f)\n", p10[i], p90[i];
    }
}'