import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class FindLastOccurrence{
  public static Integer findLastOccurrence(List<Integer> a, int x){
    for (int i = a.size() - 1; i >= 0; i--){
      if (a.get(i).equals(x)){
        return i;
      }
    }
    return -1;
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
        List<Integer> arg00 = Arrays.asList(2, 5, 5, 5, 6, 6, 8, 9, 9, 9);
        int arg01 = 5;
        int x0 = FindLastOccurrence.findLastOccurrence(Arrays.asList(2, 5, 5, 5, 6, 6, 8, 9, 9, 9), 5);
        int v0 = 3;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<Integer> arg10 = Arrays.asList(2, 3, 5, 8, 6, 6, 8, 9, 9, 9);
        int arg11 = 9;
        int x1 = FindLastOccurrence.findLastOccurrence(Arrays.asList(2, 3, 5, 8, 6, 6, 8, 9, 9, 9), 9);
        int v1 = 9;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<Integer> arg20 = Arrays.asList(2, 2, 1, 5, 6, 6, 6, 9, 9, 9);
        int arg21 = 6;
        int x2 = FindLastOccurrence.findLastOccurrence(Arrays.asList(2, 2, 1, 5, 6, 6, 6, 9, 9, 9), 6);
        int v2 = 6;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
