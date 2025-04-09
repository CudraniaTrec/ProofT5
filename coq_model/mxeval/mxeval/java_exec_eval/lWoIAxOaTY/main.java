import java.io.*;
import java.lang.*;
import java.util.*;
import java.math.*;
class CheckKElements {
    public static Boolean checkKElements(List<List<Integer>> testList, int k) {
        for ( int i = 0;i < testList.size(); i++ ) {
            for ( int j = 0;j < testList.get(i).size(); j++ ) {
                if ( testList.get(i).get(j) == k ) {
                    return true;
                }
            }
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
        List<List<Integer>> arg00 = Arrays.asList(Arrays.asList(4, 4), Arrays.asList(4, 4, 4), Arrays.asList(4, 4), Arrays.asList(4, 4, 4, 4), Arrays.asList(4));
        int arg01 = 4;
        Boolean x0 = CheckKElements.checkKElements(Arrays.asList(Arrays.asList(4, 4), Arrays.asList(4, 4, 4), Arrays.asList(4, 4), Arrays.asList(4, 4, 4, 4), Arrays.asList(4)), 4);
        Boolean v0 = true;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<List<Integer>> arg10 = Arrays.asList(Arrays.asList(7, 7, 7), Arrays.asList(7, 7));
        int arg11 = 7;
        Boolean x1 = CheckKElements.checkKElements(Arrays.asList(Arrays.asList(7, 7, 7), Arrays.asList(7, 7)), 7);
        Boolean v1 = true;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<List<Integer>> arg20 = Arrays.asList(Arrays.asList(9, 9), Arrays.asList(9, 9, 9, 9));
        int arg21 = 7;
        Boolean x2 = CheckKElements.checkKElements(Arrays.asList(Arrays.asList(9, 9), Arrays.asList(9, 9, 9, 9)), 7);
        Boolean v2 = false;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
