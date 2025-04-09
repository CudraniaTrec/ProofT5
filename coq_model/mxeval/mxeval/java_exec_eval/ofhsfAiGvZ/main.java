import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class SumPairs{
  public static Integer sumPairs(List<Integer> arr, int n){
    int sum = 0;
    for (int i = 0; i < n; i++){
      for (int j = i + 1; j < n; j++){
        sum = sum + Math.abs(arr.get(i) - arr.get(j));
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
        List<Integer> arg00 = Arrays.asList(1, 8, 9, 15, 16);
        int arg01 = 5;
        int x0 = SumPairs.sumPairs(Arrays.asList(1, 8, 9, 15, 16), 5);
        int v0 = 74;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<Integer> arg10 = Arrays.asList(1, 2, 3, 4);
        int arg11 = 4;
        int x1 = SumPairs.sumPairs(Arrays.asList(1, 2, 3, 4), 4);
        int v1 = 10;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<Integer> arg20 = Arrays.asList(1, 2, 3, 4, 5, 7, 9, 11, 14);
        int arg21 = 9;
        int x2 = SumPairs.sumPairs(Arrays.asList(1, 2, 3, 4, 5, 7, 9, 11, 14), 9);
        int v2 = 188;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
