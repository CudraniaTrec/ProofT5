import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class AverageOdd{
  public static int averageOdd(int n){
    if (n == 1){
      return 0;
    }
    int sum = 0;
    for (int i = 1; i <= n; i++){
      sum = sum + i;
    }
    return sum / n;
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
        int arg00 = 9;
        int x0 = AverageOdd.averageOdd(9);
        int v0 = 5;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        int arg10 = 5;
        int x1 = AverageOdd.averageOdd(5);
        int v1 = 3;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        int arg20 = 11;
        int x2 = AverageOdd.averageOdd(11);
        int v2 = 6;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
