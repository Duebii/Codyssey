input_a = int(input("첫번째 숫자를 입력해주세요: "))
input_b = int(input("두번째 숫자를 입력해주세요: "))
print("입력한 첫번째 숫자: ", input_a)
print("입력한 두번째 숫자: ", input_b)

print("첫번째 숫자 타입 : ", type(input_a))
print("두번째 숫자 타입 : ", type(input_b))

if input_a == input_b:
    print("두 숫자가 같습니다.")   
elif input_a > input_b:
    print("첫번째 숫자가 더 큽니다.")
elif input_a < input_b:
    print("두번째 숫자가 더 큽니다.")  
else:
    print("잘못된 입력입니다.")
    