#sleep 10
python clean_global_aircraft.py --truncate
while [ 1 ]
do
    python clean_global_aircraft.py &
    i=0
    while [ $i -le 6  ]
    do
        python get_global_positions.py &
        sleep 15
        i=$(( $i + 1 ))
    done
done