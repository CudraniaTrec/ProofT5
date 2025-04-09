import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class CheckSubset{
  public static Boolean checkSubset(List<Integer> testTup1, List<Integer> testTup2){
    HashSet<Integer> set = new HashSet<Integer>();
    for (int i = 0; i < testTup1.size(); i++){
      if (set.contains(testTup1.get(i))){
        return true;
      }
      set.add(testTup1.get(i));
    }
    for (int i = 0; i < testTup2.size(); i++){
      if (set.contains(testTup2.get(i))){
        return true;
      }
      set.add(testTup2.get(i));
    }
    return false;
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
        List<Integer> arg00 = Arrays.asList(10, 4, 5, 6);
        List<Integer> arg01 = Arrays.asList(5, 10);
        Boolean x0 = CheckSubset.checkSubset(Arrays.asList(10, 4, 5, 6), Arrays.asList(5, 10));
        Boolean v0 = true;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<Integer> arg10 = Arrays.asList(1, 2, 3, 4);
        List<Integer> arg11 = Arrays.asList(5, 6);
        Boolean x1 = CheckSubset.checkSubset(Arrays.asList(1, 2, 3, 4), Arrays.asList(5, 6));
        Boolean v1 = false;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<Integer> arg20 = Arrays.asList(7, 8, 9, 10);
        List<Integer> arg21 = Arrays.asList(10, 8);
        Boolean x2 = CheckSubset.checkSubset(Arrays.asList(7, 8, 9, 10), Arrays.asList(10, 8));
        Boolean v2 = true;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
