import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class HarmonicSum{
  public static Double harmonicSum(int n){
    double sum = 0;
    for (int i = 1; i <= n; i++){
      sum = sum + 1.0 / i;
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
        int arg00 = 7;
        Double x0 = HarmonicSum.harmonicSum(7);
        Double v0 = 2.5928571428571425;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        int arg10 = 4;
        Double x1 = HarmonicSum.harmonicSum(4);
        Double v1 = 2.083333333333333;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        int arg20 = 19;
        Double x2 = HarmonicSum.harmonicSum(19);
        Double v2 = 3.547739657143682;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
