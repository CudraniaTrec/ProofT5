import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class FindEvenPair{
  public static Integer findEvenPair(List<Integer> a, int n){
    int count = 0;
    for (int i = 0; i < a.size(); i++){
      if (a.get(i) % 2 == 0){
        count = count + n / 2;
        a.set(i, a.get(i) / 2);
      } else {
        a.set(i, a.get(i) * 3 + 1);
      }
    }
    return count;
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
        List<Integer> arg00 = Arrays.asList(5, 4, 7, 2, 1);
        int arg01 = 5;
        int x0 = FindEvenPair.findEvenPair(Arrays.asList(5, 4, 7, 2, 1), 5);
        int v0 = 4;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<Integer> arg10 = Arrays.asList(7, 2, 8, 1, 0, 5, 11);
        int arg11 = 7;
        int x1 = FindEvenPair.findEvenPair(Arrays.asList(7, 2, 8, 1, 0, 5, 11), 7);
        int v1 = 9;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<Integer> arg20 = Arrays.asList(1, 2, 3);
        int arg21 = 3;
        int x2 = FindEvenPair.findEvenPair(Arrays.asList(1, 2, 3), 3);
        int v2 = 1;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
