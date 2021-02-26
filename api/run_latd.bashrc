i=0
while [ $i -le 10000 ]
do
    python local_ac_to_database.py
    sleep 5
    i=$(( $i + 1 ))
done