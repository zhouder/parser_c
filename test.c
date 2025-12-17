#include <stdio.h>

struct student{
    char* name;   // 姓名
    int num;      // 学号
    int age;      // 年龄
    float score;  // 成绩
};

void main(){
    int i, num_140 = 0;
    float sum = 0;
    student sts[2] = {{"li ping", 5, 18, 145.0},
                      {"wang ming", 6, 18, 150.0}};
    if(sts[1].score < 140) flag = -1;
    else flag = 1;
    printf("%d", flag);
}
