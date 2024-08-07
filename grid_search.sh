#!/bin/bash

# Define parameter ranges
dims=(20 150 200 250)
lrs=(1e-3 5e-4 1e-4 5e-5)
batches=(64 32 16 4)

# Iterate through parameter combinations
for dim in "${dims[@]}"; do
    for lr in "${lrs[@]}"; do
        for batch in "${batches[@]}"; do
            echo "Running with dim=$dim, lr=$lr, batch=$batch"
            python main.py --model=BertBpr_v2 --device=cuda --comment=v2_final --dim=$dim --lr=$lr --batch=$batch
            echo "---------------------------------------------------"
        done
    done
done 