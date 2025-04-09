import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class FindMax{
  public static Integer findMax(List<Integer> arr, int low, int high){
    int max = 0;
    for (int i = low; i <= high; i++){
      max = Math.max(max, arr.get(i));
    }
    return max;
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
        List<Integer> arg00 = Arrays.asList(2, 3, 5, 6, 9);
        int arg01 = 0;
        int arg02 = 4;
        int x0 = FindMax.findMax(Arrays.asList(2, 3, 5, 6, 9), 0, 4);
        int v0 = 9;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<Integer> arg10 = Arrays.asList(3, 4, 5, 2, 1);
        int arg11 = 0;
        int arg12 = 4;
        int x1 = FindMax.findMax(Arrays.asList(3, 4, 5, 2, 1), 0, 4);
        int v1 = 5;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<Integer> arg20 = Arrays.asList(1, 2, 3);
        int arg21 = 0;
        int arg22 = 2;
        int x2 = FindMax.findMax(Arrays.asList(1, 2, 3), 0, 2);
        int v2 = 3;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
