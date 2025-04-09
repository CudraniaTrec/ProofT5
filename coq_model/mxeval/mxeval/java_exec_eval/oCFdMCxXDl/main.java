import java.io.*;
import java.lang.*;
import java.util.*;
import java.math.*;
class Sumoffactors {
    public static Integer sumoffactors(int n) {
        int sum = 0;
        for ( int i = 2;i <= n; i += 2 ) {
            if ( n % i == 0 ) {
                sum += i;
            }
        }
        return sum;
    }
}


class Main {
    public static boolean compare(Object obj1, Object obj2) {
        if (obj1 == null && obj2 == null){
            return true;
        } else if (obj1 == null || obj2 == null){
            return false;
        } else {
            return obj1.equals(obj2);
        }
    }
    
    public static void main(String[] args) throws Exception {
        int arg00 = 18;
        int x0 = Sumoffactors.sumoffactors(18);
        int v0 = 26;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        int arg10 = 30;
        int x1 = Sumoffactors.sumoffactors(30);
        int v1 = 48;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        int arg20 = 6;
        int x2 = Sumoffactors.sumoffactors(6);
        int v2 = 8;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
