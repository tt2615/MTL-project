#!/bin/bash

# Define parameter ranges
dims=(150 200 250)
lrs=(5e-4 1e-4 5e-5)
batches=(64 32 16 4)

# Iterate through parameter combinations
for dim in "${dims[@]}"; do
    for lr in "${lrs[@]}"; do
        for batch in "${batches[@]}"; do
            echo "Running with dim=$dim, lr=$lr, batch=$batch"
            python main.py --model=BertBpr --device=cuda --comment=grid_full --dim=$dim --lr=$lr --batch=$batch
            echo "---------------------------------------------------"
        done
    done
done 